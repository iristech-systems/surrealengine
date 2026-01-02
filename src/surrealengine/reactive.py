import asyncio
from typing import TypeVar, AsyncGenerator, List, Dict, Any, Optional, Union
from .events import LiveEvent
from .query.base import QuerySet
from surrealdb import RecordID
import logging

T = TypeVar("T")

logger = logging.getLogger(__name__)

class ReactiveChange:
    """Represents a change in the reactive collection."""
    def __init__(self, event: LiveEvent, current_items: List[Any]):
        self.event = event
        self.current_items = current_items
        
    @property
    def is_create(self) -> bool:
        return self.event.is_create

    @property
    def is_update(self) -> bool:
        return self.event.is_update
        
    @property
    def is_delete(self) -> bool:
        return self.event.is_delete
        
    @property
    def document(self) -> Any:
        """The document associated with the change (if available)."""
        # For DELETE, this might just be the ID wrapper if we don't have the old doc
        return self.event.data

class ReactiveQuerySet:
    """
    A reactive wrapper around a QuerySet that maintains a real-time local cache of the data.
    
    It performs an initial fetch (snapshot) and then subscribes to Live Queries to
    apply updates automatically.
    """
    def __init__(self, queryset: QuerySet):
        self._queryset = queryset
        # Clone queryset to ensure it's isolated
        self._queryset = queryset._clone()
        
        # The local cache
        self._items: List[Any] = []
        self._id_map: Dict[str, Any] = {}
        
        # Capture sort/limit configuration
        self._order_by = self._queryset.order_by_value
        self._limit = self._queryset.limit_value
        
        # State
        self._live_query_id = None
        self._listening = False
        self._initial_sync_done = False
        
    async def sync(self):
        """
        Perform the initial snapshot fetch and start the live subscription.
        Must be called before accessing items or watching.
        """
        if self._initial_sync_done:
            return

        # 1. Start the Live Query FIRST to buffer events while we fetch snapshot
        # Note: In standard SDK we can't easily "buffer" before the loop, 
        # so this is a simplified v1 where we fetch then listen. 
        # Race condition warning: events happening during fetch might be lost 
        # or duplicated. Ideally we'd start the live cursor, buffer, then fetch.
        
        # For v1 simplicity: Fetch Snapshot
        self._items = await self._queryset.all()
        self._rebuild_map()
        self._initial_sync_done = True
        
    def _rebuild_map(self):
        """Rebuild the ID map for O(1) lookups."""
        self._id_map = {}
        for item in self._items:
            if hasattr(item, 'id') and item.id:
                self._id_map[str(item.id)] = item

    async def watch(self) -> AsyncGenerator[ReactiveChange, None]:
        """
        Async generator that yields control whenever the collection changes.
        """
        if not self._initial_sync_done:
            await self.sync()
            
        # We listen to the SAME queryset filters
        # Note: QuerySet.live() currently returns an async generator
        async for event in self._queryset.live():
            self._apply_change(event)
            yield ReactiveChange(event, self._items)
            
    def _apply_change(self, event: LiveEvent):
        """Apply a LiveEvent to the local cache."""
        doc_id = str(event.id) if event.id else None
        
        if event.is_create:
            # Parse the new document
            # The event.data is a dict usually. We need to convert to Document.
            try:
                # We assume event.data is the full record content
                new_doc = self._queryset.document_class.from_db(event.data)
                
                # Check if it already exists (race condition or dupe)
                if doc_id and doc_id in self._id_map:
                    # Update existing instead of appending duplicate
                    existing = self._id_map[doc_id]
                    # Update fields
                    existing._data.update(new_doc._data)
                    existing._original_data = existing._data.copy()
                    existing._changed_fields = []
                else:
                    self._items.append(new_doc)
                    if doc_id:
                        self._id_map[doc_id] = new_doc
            except Exception as e:
                logger.error(f"Failed to apply CREATE patch: {e}")

        elif event.is_update:
            if doc_id and doc_id in self._id_map:
                existing = self._id_map[doc_id]
                try:
                    updated_doc = self._queryset.document_class.from_db(event.data)
                    # Update fields in place
                    existing._data.update(updated_doc._data)
                    existing._original_data = existing._data.copy()
                    existing._changed_fields = []
                except Exception as e:
                     logger.error(f"Failed to apply UPDATE patch: {e}")
            else:
                # We received an update for an object we don't have. 
                try:
                    new_doc = self._queryset.document_class.from_db(event.data)
                    self._items.append(new_doc)
                    if doc_id:
                        self._id_map[doc_id] = new_doc
                except Exception:
                    pass

        elif event.is_delete:
            if doc_id and doc_id in self._id_map:
                existing = self._id_map[doc_id]
                self._items.remove(existing)
                del self._id_map[doc_id]

        # Enforce Sort and Limit
        self._enforce_constraints()

    def _enforce_constraints(self):
        """Sort and limit the items list based on queryset configuration."""
        # 1. Sort
        if self._order_by:
            field, direction = self._order_by
            reverse = (direction.upper() == 'DESC')
            try:
                def get_sort_key(item):
                    if hasattr(item, field):
                        val = getattr(item, field)
                        if callable(val): return None
                        return val
                    if hasattr(item, '_data') and isinstance(item._data, dict):
                        return item._data.get(field)
                    return None
                
                self._items.sort(key=get_sort_key, reverse=reverse)
            except Exception as e:
                logger.warning(f"Failed to sort reactive list by {field}: {e}")

        # 2. Limit
        if self._limit is not None and len(self._items) > self._limit:
            removed = self._items[self._limit:]
            self._items = self._items[:self._limit]
            
            # Clean up ID map for removed items
            for item in removed:
                if hasattr(item, 'id') and item.id:
                    rid = str(item.id)
                    if rid in self._id_map:
                        del self._id_map[rid]
    
    @property
    def items(self) -> List[Any]:
        """Return the current list of items."""
        return self._items
        
    def to_pandas(self):
        """Convert current state to Pandas DataFrame."""
        try:
            import pandas as pd
            # Use to_db() or __dict__?
            # to_db() gives serialization-safe data
            data = [item.to_db() for item in self._items]
            return pd.DataFrame(data)
        except ImportError:
            raise ImportError("pandas is required for to_pandas()")
