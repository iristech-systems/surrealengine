from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional
from surrealdb import RecordID

@dataclass
class LiveEvent:
    """Represents a live query event from SurrealDB."""
    action: str
    data: Dict[str, Any]
    ts: Optional[datetime] = None
    id: Optional[RecordID] = None
    
    @property
    def is_create(self) -> bool:
        return self.action == "CREATE"

    @property
    def is_update(self) -> bool:
        return self.action == "UPDATE"

    @property
    def is_delete(self) -> bool:
        return self.action == "DELETE"
