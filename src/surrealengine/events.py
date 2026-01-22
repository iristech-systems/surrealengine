from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional, Union, List
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


@dataclass
class Event:
    """
    Defines a SurrealDB Event (trigger) for schema definition.

    Events are triggered by changes to the table and can execute SurrealQL logic.

    Attributes:
        name (str): The name of the event.
        when (str): The condition under which the event triggers.
                    Can be a raw SurrealQL condition string (e.g., "$event = 'CREATE'").
        then (Union[str, List[str]]): The SurrealQL statement(s) to execute when logic invokes.
                                      Can be a single string or a list of statements.
    """
    name: str
    when: str
    then: Union[str, List[str]]

    def to_sql(self, table_name: str) -> str:
        """
        Generate the DEFINE EVENT SurrealQL statement.
        """
        query = f"DEFINE EVENT {self.name} ON TABLE {table_name} WHEN {self.when} THEN "
        
        if isinstance(self.then, list):
            # Block of statements
            statements = "; ".join(self.then)
            query += f"{{ {statements} }}"
        else:
            # Single statement or block provided as string
            query += self.then
            
        return query
