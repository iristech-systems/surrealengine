import datetime
import json
from typing import Any, Dict, List, Optional, Tuple, Type, Union, cast
from surrealdb import RecordID


class RelationQuerySet:
    """Query set specifically for graph relations.

    This class provides methods for querying and manipulating graph relations
    between documents in the database. It allows creating, retrieving, updating,
    and deleting relations between documents.

    Attributes:
        from_document: The document class the relation is from
        connection: The database connection to use for queries
        relation: The name of the relation
        query_parts: List of query parts
    """

    def __init__(self, from_document: Type, connection: Any, relation: Optional[str] = None) -> None:
        """Initialize a new RelationQuerySet.

        Args:
            from_document: The document class the relation is from
            connection: The database connection to use for queries
            relation: The name of the relation
        """
        self.from_document = from_document
        self.connection = connection
        self.relation = relation
        self.query_parts: List[Any] = []

    async def relate(self, from_instance: Any, to_instance: Any, **attrs: Any) -> Optional[Any]:
        """Create a relation between two instances asynchronously.

        This method creates a relation between two document instances in the database.
        It constructs a RELATE query with the given relation name and attributes.

        Args:
            from_instance: The instance to create the relation from
            to_instance: The instance to create the relation to
            **attrs: Attributes to set on the relation

        Returns:
            The created relation record or None if creation failed

        Raises:
            ValueError: If either instance is not saved or if no relation name is specified
        """
        if not from_instance.id:
            raise ValueError(f"Cannot create relation from unsaved {self.from_document.__name__}")

        to_class = to_instance.__class__
        if not to_instance.id:
            raise ValueError(f"Cannot create relation to unsaved {to_class.__name__}")

        # Handle both string and RecordID types for IDs
        if isinstance(from_instance.id, RecordID):
            from_id = str(from_instance.id).split(':')[1]
            from_collection = from_instance.id.table_name
        else:
            from_id = from_instance.id.split(':')[1] if ':' in from_instance.id else from_instance.id
            from_collection = self.from_document._get_collection_name()

        if isinstance(to_instance.id, RecordID):
            to_id = str(to_instance.id).split(':')[1]
            to_collection = to_instance.id.table_name
        else:
            to_id = to_instance.id.split(':')[1] if ':' in to_instance.id else to_instance.id
            to_collection = to_class._get_collection_name()

        # Create RecordID objects with the correct collection names and IDs
        from_record = RecordID(from_collection, from_id)
        to_record = RecordID(to_collection, to_id)

        relation = self.relation
        if not relation:
            raise ValueError("Relation name must be specified")

        # Construct the relation query using the RecordID objects
        query = f"RELATE {from_record}->{relation}->{to_record}"

        # Add attributes if provided
        if attrs:
            # Convert datetime objects to ISO format for JSON serialization
            processed_attrs = {}
            for k, v in attrs.items():
                if isinstance(v, datetime.datetime):
                    processed_attrs[k] = v.isoformat()
                else:
                    processed_attrs[k] = v
            
            from ..document import _serialize_for_surreal as _ser
            attrs_str = ", ".join([f"{k}: {_ser(v)}" for k, v in processed_attrs.items()])
            query += f" CONTENT {{ {attrs_str} }}"

        result = await self.connection.client.query(query)

        # Return the relation record
        if result and result[0]:
            return result[0]

        return None

    def relate_sync(self, from_instance: Any, to_instance: Any, **attrs: Any) -> Optional[Any]:
        """Create a relation between two instances synchronously.

        This method creates a relation between two document instances in the database.
        It constructs a RELATE query with the given relation name and attributes.

        Args:
            from_instance: The instance to create the relation from
            to_instance: The instance to create the relation to
            **attrs: Attributes to set on the relation

        Returns:
            The created relation record or None if creation failed

        Raises:
            ValueError: If either instance is not saved or if no relation name is specified
        """
        if not from_instance.id:
            raise ValueError(f"Cannot create relation from unsaved {self.from_document.__name__}")

        to_class = to_instance.__class__
        if not to_instance.id:
            raise ValueError(f"Cannot create relation to unsaved {to_class.__name__}")

        # Handle both string and RecordID types for IDs
        if isinstance(from_instance.id, RecordID):
            from_id = str(from_instance.id).split(':')[1]
            from_collection = from_instance.id.table_name
        else:
            from_id = from_instance.id.split(':')[1] if ':' in from_instance.id else from_instance.id
            from_collection = self.from_document._get_collection_name()

        if isinstance(to_instance.id, RecordID):
            to_id = str(to_instance.id).split(':')[1]
            to_collection = to_instance.id.table_name
        else:
            to_id = to_instance.id.split(':')[1] if ':' in to_instance.id else to_instance.id
            to_collection = to_class._get_collection_name()

        # Create RecordID objects with the correct collection names and IDs
        from_record = RecordID(from_collection, from_id)
        to_record = RecordID(to_collection, to_id)

        relation = self.relation
        if not relation:
            raise ValueError("Relation name must be specified")

        # Construct the relation query using the RecordID objects
        query = f"RELATE {from_record}->{relation}->{to_record}"

        # Add attributes if provided
        if attrs:
            # Convert datetime objects to ISO format for JSON serialization
            processed_attrs = {}
            for k, v in attrs.items():
                if isinstance(v, datetime.datetime):
                    processed_attrs[k] = v.isoformat()
                else:
                    processed_attrs[k] = v
            
            from ..document import _serialize_for_surreal as _ser
            attrs_str = ", ".join([f"{k}: {_ser(v)}" for k, v in processed_attrs.items()])
            query += f" CONTENT {{ {attrs_str} }}"

        result = self.connection.client.query(query)

        # Return the relation record
        if result and result[0]:
            return result[0]

        return None

    async def get_related(self, instance: Any, target_document: Optional[Type] = None, **filters: Any) -> List[Any]:
        """Get related documents asynchronously.

        This method retrieves documents related to the given instance through
        the specified relation. It can return either the target documents or
        the relation records themselves.

        Args:
            instance: The instance to get related documents for
            target_document: The document class of the target documents (optional)
            **filters: Filters to apply to the related documents

        Returns:
            List of related documents or relation records

        Raises:
            ValueError: If the instance is not saved or if no relation name is specified
        """
        if not instance.id:
            raise ValueError(f"Cannot get relations for unsaved {self.from_document.__name__}")

        relation = self.relation
        if not relation:
            raise ValueError("Relation name must be specified")

        # Handle both string and RecordID types for IDs
        if isinstance(instance.id, RecordID):
            from_id = str(instance.id)
        else:
            from_id = instance.id if ':' in instance.id else f"{self.from_document._get_collection_name()}:{instance.id}"

        # Construct the graph traversal query using the correct SurrealQL syntax
        if target_document:
            # When we want to get the target documents
            target_collection = target_document._get_collection_name()
            query = f"SELECT ->{relation}->{target_collection} FROM {from_id}"
        else:
            # When we just want the relations
            query = f"SELECT id, ->{relation}->? as related FROM {from_id}"

        # Add additional filters if provided
        if filters:
            conditions = []
            for field, value in filters.items():
                from ..surrealql import escape_literal
                conditions.append(f"{field} = {escape_literal(value)}")
            query += f" WHERE {' AND '.join(conditions)}"
        
        result = await self.connection.client.query(query)
        if not result or not result[0]:
            return []

        # Process results based on query type
        if target_document:
            # When target_document is specified, we're getting actual documents
            return [target_document.from_db(doc) for doc in result[0]]
        else:
            # When no target_document, we're getting relation data
            return result[0]

    def get_related_sync(self, instance: Any, target_document: Optional[Type] = None, **filters: Any) -> List[Any]:
        """Get related documents synchronously.

        This method retrieves documents related to the given instance through
        the specified relation. It can return either the target documents or
        the relation records themselves.

        Args:
            instance: The instance to get related documents for
            target_document: The document class of the target documents (optional)
            **filters: Filters to apply to the related documents

        Returns:
            List of related documents or relation records

        Raises:
            ValueError: If the instance is not saved or if no relation name is specified
        """
        if not instance.id:
            raise ValueError(f"Cannot get relations for unsaved {self.from_document.__name__}")

        relation = self.relation
        if not relation:
            raise ValueError("Relation name must be specified")

        # Handle both string and RecordID types for IDs
        if isinstance(instance.id, RecordID):
            from_id = str(instance.id)
        else:
            from_id = instance.id if ':' in instance.id else f"{self.from_document._get_collection_name()}:{instance.id}"

        # Construct the graph traversal query using the correct SurrealQL syntax
        if target_document:
            # When we want to get the target documents
            target_collection = target_document._get_collection_name()
            query = f"SELECT ->{relation}->{target_collection} FROM {from_id}"
        else:
            # When we just want the relations
            query = f"SELECT id, ->{relation}->? as related FROM {from_id}"

        # Add additional filters if provided
        if filters:
            conditions = []
            for field, value in filters.items():
                from ..surrealql import escape_literal
                conditions.append(f"{field} = {escape_literal(value)}")
            query += f" WHERE {' AND '.join(conditions)}"
        
        result = self.connection.client.query(query)

        if not result or not result[0]:
            return []

        # Process results based on query type
        if target_document:
            # When target_document is specified, we're getting actual documents
            return [target_document.from_db(doc) for doc in result[0]]
        else:
            # When no target_document, we're getting relation data
            return result[0]

    async def update_relation(self, from_instance: Any, to_instance: Any, **attrs: Any) -> Optional[Any]:
        """Update an existing relation asynchronously.

        This method updates an existing relation between two document instances
        in the database. If the relation doesn't exist, it creates it.

        Args:
            from_instance: The instance the relation is from
            to_instance: The instance the relation is to
            **attrs: Attributes to update on the relation

        Returns:
            The updated relation record or None if update failed

        Raises:
            ValueError: If either instance is not saved or if no relation name is specified
        """
        if not from_instance.id or not to_instance.id:
            raise ValueError("Cannot update relation between unsaved documents")

        relation = self.relation
        if not relation:
            raise ValueError("Relation name must be specified")

        # Handle both string and RecordID types for IDs
        if isinstance(from_instance.id, RecordID):
            from_id = str(from_instance.id)
        else:
            from_id = f"{self.from_document._get_collection_name()}:{from_instance.id}"

        to_class = to_instance.__class__
        if isinstance(to_instance.id, RecordID):
            to_id = str(to_instance.id)
        else:
            to_id = f"{to_class._get_collection_name()}:{to_instance.id}"

        # Query the relation first
        from ..surrealql import escape_literal
        relation_query = f"SELECT id FROM {relation} WHERE in = {escape_literal(from_id)} AND out = {escape_literal(to_id)}"
        relation_result = await self.connection.client.query(relation_query)

        if not relation_result or not relation_result[0]:
            return await self.relate(from_instance, to_instance, **attrs)

        # Get relation ID and update
        relation_id = relation_result[0][0]['id']
        update_query = f"UPDATE {relation_id} SET"

        # Add attributes
        updates = []
        from ..document import _serialize_for_surreal as _ser
        for key, value in attrs.items():
            updates.append(f" {key} = {_ser(value)}")

        update_query += ",".join(updates)

        result = await self.connection.client.query(update_query)

        if result and result[0]:
            return result[0][0]

        return None

    def update_relation_sync(self, from_instance: Any, to_instance: Any, **attrs: Any) -> Optional[Any]:
        """Update an existing relation synchronously.

        This method updates an existing relation between two document instances
        in the database. If the relation doesn't exist, it creates it.

        Args:
            from_instance: The instance the relation is from
            to_instance: The instance the relation is to
            **attrs: Attributes to update on the relation

        Returns:
            The updated relation record or None if update failed

        Raises:
            ValueError: If either instance is not saved or if no relation name is specified
        """
        if not from_instance.id or not to_instance.id:
            raise ValueError("Cannot update relation between unsaved documents")

        relation = self.relation
        if not relation:
            raise ValueError("Relation name must be specified")

        # Handle both string and RecordID types for IDs
        if isinstance(from_instance.id, RecordID):
            from_id = str(from_instance.id)
        else:
            from_id = f"{self.from_document._get_collection_name()}:{from_instance.id}"

        to_class = to_instance.__class__
        if isinstance(to_instance.id, RecordID):
            to_id = str(to_instance.id)
        else:
            to_id = f"{to_class._get_collection_name()}:{to_instance.id}"

        # Query the relation first
        from ..surrealql import escape_literal
        relation_query = f"SELECT id FROM {relation} WHERE in = {escape_literal(from_id)} AND out = {escape_literal(to_id)}"
        relation_result = self.connection.client.query(relation_query)

        if not relation_result or not relation_result[0]:
            return self.relate_sync(from_instance, to_instance, **attrs)

        # Get relation ID and update
        relation_id = relation_result[0][0]['id']
        update_query = f"UPDATE {relation_id} SET"

        # Add attributes
        updates = []
        from ..document import _serialize_for_surreal as _ser
        for key, value in attrs.items():
            updates.append(f" {key} = {_ser(value)}")

        update_query += ",".join(updates)

        result = self.connection.client.query(update_query)

        if result and result[0]:
            return result[0][0]

        return None

    async def delete_relation(self, from_instance: Any, to_instance: Optional[Any] = None) -> int:
        """Delete a relation asynchronously.

        This method deletes a relation between two document instances in the database.
        If to_instance is not provided, it deletes all relations from from_instance.

        Args:
            from_instance: The instance the relation is from
            to_instance: The instance the relation is to (optional)

        Returns:
            Number of deleted relations

        Raises:
            ValueError: If from_instance is not saved, if to_instance is provided but not saved,
                       or if no relation name is specified
        """
        if not from_instance.id:
            raise ValueError(f"Cannot delete relation for unsaved {self.from_document.__name__}")

        relation = self.relation
        if not relation:
            raise ValueError("Relation name must be specified")

        # Handle both string and RecordID types for from_instance ID
        if isinstance(from_instance.id, RecordID):
            from_id = str(from_instance.id)
        else:
            from_id = f"{self.from_document._get_collection_name()}:{from_instance.id}"

        # Construct the delete query
        if to_instance:
            if not to_instance.id:
                raise ValueError("Cannot delete relation to unsaved document")

            # Handle both string and RecordID types for to_instance ID
            to_class = to_instance.__class__
            if isinstance(to_instance.id, RecordID):
                to_id = str(to_instance.id)
            else:
                to_id = f"{to_class._get_collection_name()}:{to_instance.id}"

            # Delete specific relation
            from ..surrealql import escape_literal
            query = f"DELETE FROM {relation} WHERE in = {escape_literal(from_id)} AND out = {escape_literal(to_id)}"
        else:
            # Delete all relations from this instance
            from ..surrealql import escape_literal
            query = f"DELETE FROM {relation} WHERE in = {escape_literal(from_id)}"

        result = await self.connection.client.query(query)

        if result and result[0]:
            return len(result[0])

        return 0

    def delete_relation_sync(self, from_instance: Any, to_instance: Optional[Any] = None) -> int:
        """Delete a relation synchronously.

        This method deletes a relation between two document instances in the database.
        If to_instance is not provided, it deletes all relations from from_instance.

        Args:
            from_instance: The instance the relation is from
            to_instance: The instance the relation is to (optional)

        Returns:
            Number of deleted relations

        Raises:
            ValueError: If from_instance is not saved, if to_instance is provided but not saved,
                       or if no relation name is specified
        """
        if not from_instance.id:
            raise ValueError(f"Cannot delete relation for unsaved {self.from_document.__name__}")

        relation = self.relation
        if not relation:
            raise ValueError("Relation name must be specified")

        # Handle both string and RecordID types for from_instance ID
        if isinstance(from_instance.id, RecordID):
            from_id = str(from_instance.id)
        else:
            from_id = f"{self.from_document._get_collection_name()}:{from_instance.id}"

        # Construct the delete query
        if to_instance:
            if not to_instance.id:
                raise ValueError("Cannot delete relation to unsaved document")

            # Handle both string and RecordID types for to_instance ID
            to_class = to_instance.__class__
            if isinstance(to_instance.id, RecordID):
                to_id = str(to_instance.id)
            else:
                to_id = f"{to_class._get_collection_name()}:{to_instance.id}"

            # Delete specific relation
            from ..surrealql import escape_literal
            query = f"DELETE FROM {relation} WHERE in = {escape_literal(from_id)} AND out = {escape_literal(to_id)}"
        else:
            # Delete all relations from this instance
            from ..surrealql import escape_literal
            query = f"DELETE FROM {relation} WHERE in = {escape_literal(from_id)}"

        result = self.connection.client.query(query)

        if result and result[0]:
            return len(result[0])

        return 0