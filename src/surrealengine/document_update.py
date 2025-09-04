"""
Extension module for Document update functionality.

This module provides update methods for Document instances
that allow updating specific fields without deleting existing data.
"""

import json
import datetime
from typing import Any, Optional, Dict, Type

# Robust import for SDK datetime wrapper
try:
    from surrealdb.data.types.datetime import IsoDateTimeWrapper  # new path
except Exception:  # pragma: no cover
    try:
        from surrealdb.types import IsoDateTimeWrapper  # older path
    except Exception:
        IsoDateTimeWrapper = None

from .document import Document
from .connection import ConnectionRegistry

# Universal HTTP-safe serializer for outgoing payloads (Fix B)
def serialize_http_safe(value: Any):
    """Recursively convert datetime and IsoDateTimeWrapper into ISO Z strings for JSON HTTP payloads."""
    try:
        from surrealdb.data.types.datetime import IsoDateTimeWrapper as _Iso
    except Exception:
        try:
            from surrealdb.types import IsoDateTimeWrapper as _Iso
        except Exception:
            _Iso = ()
    import datetime as _dt
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, _dt.datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=_dt.timezone.utc)
        return value.isoformat().replace('+00:00','Z')
    if _Iso and isinstance(value, _Iso):
        inner = getattr(value, 'dt', None)
        if isinstance(inner, _dt.datetime):
            if inner.tzinfo is None:
                inner = inner.replace(tzinfo=_dt.timezone.utc)
            return inner.isoformat().replace('+00:00','Z')
        if isinstance(inner, str):
            return inner.replace('+00:00','Z')
        inner2 = getattr(value, 'iso', None)
        if isinstance(inner2, str):
            return inner2.replace('+00:00','Z')
        return str(value)
    if isinstance(value, list):
        return [serialize_http_safe(v) for v in value]
    if isinstance(value, dict):
        return {k: serialize_http_safe(v) for k, v in value.items()}
    return value


def _iso_from_wrapper(w) -> str:
    if w is None:
        return ""
    s = getattr(w, "dt", None)
    if isinstance(s, datetime.datetime):
        return s.isoformat()
    if isinstance(s, str):
        return s
    s2 = getattr(w, "iso", None)
    if isinstance(s2, str):
        return s2
    return str(w)


def _serialize_for_surreal(value: Any) -> str:
    """Serialize Python values to SurrealDB-friendly literal strings.
    - IsoDateTimeWrapper or datetime -> d'...'
    - Strings: pass through if already a Surreal literal; else JSON-quote
    - None -> none
    - Lists/Tuples/Dicts: recursive serialization
    - Primitives -> json.dumps
    """
    # Datetime wrappers and datetime objects
    if IsoDateTimeWrapper is not None and isinstance(value, IsoDateTimeWrapper):
        iso = _iso_from_wrapper(value).replace("+00:00", "Z")
        return f"d'{iso}'"
    if isinstance(value, datetime.datetime):
        # Ensure timezone awareness defaulting to UTC
        dt = value if value.tzinfo is not None else value.replace(tzinfo=datetime.timezone.utc)
        iso = dt.isoformat().replace("+00:00", "Z")
        return f"d'{iso}'"

    # Already a Surreal datetime literal
    if isinstance(value, str):
        if value.startswith("d'") and value.endswith("'"):
            return value
        return json.dumps(value)

    if value is None:
        return "none"

    if isinstance(value, list):
        return '[' + ', '.join(_serialize_for_surreal(v) for v in value) + ']'
    if isinstance(value, tuple):
        return '[' + ', '.join(_serialize_for_surreal(v) for v in value) + ']'
    if isinstance(value, dict):
        items = []
        for k, v in value.items():
            items.append(json.dumps(str(k)) + ": " + _serialize_for_surreal(v))
        return '{' + ', '.join(items) + '}'

    try:
        return json.dumps(value)
    except TypeError:
        return json.dumps(str(value))


async def update_document(doc: Document, 
                         connection: Optional[Any] = None, 
                         **attrs: Any) -> Document:
    """Update the document without deleting existing data.
    
    This method updates only the specified attributes of the document
    without affecting other attributes, unlike the save() method which uses upsert.
    
    Args:
        doc: The Document instance to update
        connection: The database connection to use (optional)
        **attrs: Attributes to update on the document
        
    Returns:
        The updated document
        
    Raises:
        ValueError: If the document is not saved
    """
    if not doc.id:
        raise ValueError("Cannot update unsaved document")
        
    if connection is None:
        connection = ConnectionRegistry.get_default_connection(async_mode=True)
        
    # Update only the specified attributes
    update_query = f"UPDATE {doc.id} SET"
    
    # Add attributes
    updates = []
    for key, value in attrs.items():
        # Update the instance
        setattr(doc, key, value)
        # Use field's to_db if available before serialization
        field_obj = getattr(doc, '_fields', {}).get(key)
        db_value = field_obj.to_db(value) if field_obj is not None else value
        updates.append(f" {key} = {_serialize_for_surreal(db_value)}")
        
    if not updates:
        return doc
        
    update_query += ",".join(updates)
    
    result = await connection.client.query(update_query)
    
    if result and result[0]:
        # Mark the updated fields as clean
        for key in attrs:
            if key in doc._changed_fields:
                doc._changed_fields.remove(key)
                
        # Update the original values
        for key, value in attrs.items():
            if hasattr(doc, '_original_data'):
                doc._original_data[key] = value
            
    return doc
    
def update_document_sync(doc: Document, 
                        connection: Optional[Any] = None, 
                        **attrs: Any) -> Document:
    """Update the document without deleting existing data synchronously.
    
    This method updates only the specified attributes of the document
    without affecting other attributes, unlike the save() method which uses upsert.
    
    Args:
        doc: The Document instance to update
        connection: The database connection to use (optional)
        **attrs: Attributes to update on the document
        
    Returns:
        The updated document
        
    Raises:
        ValueError: If the document is not saved
    """
    if not doc.id:
        raise ValueError("Cannot update unsaved document")
        
    if connection is None:
        connection = ConnectionRegistry.get_default_connection(async_mode=False)
        
    # Update only the specified attributes
    update_query = f"UPDATE {doc.id} SET"
    
    # Add attributes
    updates = []
    for key, value in attrs.items():
        # Update the instance
        setattr(doc, key, value)
        field_obj = getattr(doc, '_fields', {}).get(key)
        db_value = field_obj.to_db(value) if field_obj is not None else value
        updates.append(f" {key} = {_serialize_for_surreal(db_value)}")
        
    if not updates:
        return doc
        
    update_query += ",".join(updates)
    
    result = connection.client.query(update_query)
    
    if result and result[0]:
        # Mark the updated fields as clean
        for key in attrs:
            if key in doc._changed_fields:
                doc._changed_fields.remove(key)
                
        # Update the original values
        for key, value in attrs.items():
            if hasattr(doc, '_original_data'):
                doc._original_data[key] = value
            
    return doc

# Monkey patch the Document class to add the update methods
def patch_document():
    """Add update methods to Document class and modify save methods.
    
    This function:
    1. Adds update() and update_sync() methods to Document
    2. Modifies the original save() and save_sync() methods to use update() for existing documents
    """
    # Store original save methods
    original_save = Document.save
    original_save_sync = Document.save_sync
    
    # Add update methods
    Document.update = update_document
    Document.update_sync = update_document_sync
    
    # Define new save methods that use update for existing documents
    async def new_save(self, connection=None):
        """Enhanced save method that uses update for existing or HTTP-safe create for new documents."""
        # If document exists and has changes, use update instead of upsert
        if self.id and self._changed_fields:
            data = self.get_changed_data_for_update()
            if data:
                return await self.update(**data)
        # New document: perform HTTP-safe create
        if connection is None:
            connection = ConnectionRegistry.get_default_connection(async_mode=True)
        # Full data for create
        data = self.to_db()
        safe_data = serialize_http_safe(data)
        # Execute create
        result = await connection.client.create(
            self._get_collection_name(),
            safe_data
        )
        # Apply result to instance (mirrors original save)
        if result:
            doc_data = result[0] if isinstance(result, list) and result else result
            if isinstance(doc_data, dict):
                self._data.update(doc_data)
                if 'id' in doc_data:
                    self._data['id'] = doc_data['id']
                for field_name, field in self._fields.items():
                    if field_name in doc_data:
                        self._data[field_name] = field.from_db(doc_data[field_name])
        # Mark clean
        if hasattr(self, 'mark_clean'):
            self.mark_clean()
        return self
    
    def new_save_sync(self, connection=None):
        """Enhanced sync save method that uses update for existing or HTTP-safe create for new documents."""
        if self.id and self._changed_fields:
            data = self.get_changed_data_for_update()
            if data:
                return self.update_sync(**data)
        if connection is None:
            connection = ConnectionRegistry.get_default_connection(async_mode=False)
        data = self.to_db()
        safe_data = serialize_http_safe(data)
        result = connection.client.create(
            self._get_collection_name(),
            safe_data
        )
        if result:
            doc_data = result[0] if isinstance(result, list) and result else result
            if isinstance(doc_data, dict):
                self._data.update(doc_data)
                if 'id' in doc_data:
                    self._data['id'] = doc_data['id']
                for field_name, field in self._fields.items():
                    if field_name in doc_data:
                        self._data[field_name] = field.from_db(doc_data[field_name])
        if hasattr(self, 'mark_clean'):
            self.mark_clean()
        return self
    
    # Replace save methods
    Document.save = new_save
    Document.save_sync = new_save_sync