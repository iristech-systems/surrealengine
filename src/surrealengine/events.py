from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional
from surrealdb import RecordID

@dataclass
class LiveEvent:
    """Represents a live query event from SurrealDB.

    Provides typed access to LIVE query events with action filtering
    and convenient property accessors for event types.

    Attributes:
        action: Event type (CREATE, UPDATE, DELETE)
        data: Event data dictionary containing the document fields
        ts: Optional timestamp of the event
        id: Optional RecordID of the affected document

    Example:
        ```python
        async for evt in User.objects.live(action="CREATE"):
            if evt.is_create:
                print(f"New user created: {evt.id}")
                print(f"Data: {evt.data}")
        ```
    """
    action: str
    data: Dict[str, Any]
    ts: Optional[datetime] = None
    id: Optional[RecordID] = None

    @property
    def is_create(self) -> bool:
        """Check if this event is a CREATE action."""
        return self.action == "CREATE"

    @property
    def is_update(self) -> bool:
        """Check if this event is an UPDATE action."""
        return self.action == "UPDATE"

    @property
    def is_delete(self) -> bool:
        """Check if this event is a DELETE action."""
        return self.action == "DELETE"
