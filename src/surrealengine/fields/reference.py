from typing import Any, Dict, List, Optional, Type, Union

from surrealdb import RecordID

from .base import Field

class ReferenceField(Field):
    """Reference to another document.

    This field type stores references to other documents in the database.
    It can accept a document instance, an ID string, or a dictionary with an ID.

    Attributes:
        document_type: The type of document being referenced

    Examples:
        Basic reference field:

        >>> author = ReferenceField(User, required=True)
        >>> category = ReferenceField(Category)

        Optional reference:

        >>> parent = ReferenceField(Comment)  # Self-reference
        >>> reviewer = ReferenceField(User)

        Reference with schema definition:

        >>> resident = ReferenceField(Person, define_schema=True)
        >>> organization = ReferenceField(Organization, indexed=True)

        Multiple references in a document:

        >>> class Post(Document):
        ...     author = ReferenceField(User, required=True)
        ...     category = ReferenceField(Category)
        ...     reviewer = ReferenceField(User)
    """

    def __init__(self, document_type: Type, **kwargs: Any) -> None:
        """Initialize a new ReferenceField.

        Args:
            document_type: The type of document being referenced
            required: Whether the field is required (default: False)
            default: Default value for the field
            db_field: Name of the field in the database (defaults to the field name)
            define_schema: Whether to define this field in the schema (even for SCHEMALESS tables)
            indexed: Whether the field should be indexed (default: False)
            unique: Whether the index should enforce uniqueness (default: False)
            search: Whether the index is a search index (default: False)
            analyzer: Analyzer to use for search indexes
            index_with: List of other field names to include in the index
        """
        self.document_type = document_type
        super().__init__(**kwargs)
        self.py_type = Union[Type, str, dict]

    def validate(self, value: Any) -> Any:
        """Validate the reference value.

        This method checks if the value is a valid reference to another document.
        It accepts a document instance, an ID string, a dictionary with an ID, or a RecordID object.

        Args:
            value: The value to validate

        Returns:
            The validated reference value

        Raises:
            TypeError: If the value is not a valid reference
            ValueError: If the referenced document is not saved
        """
        value = super().validate(value)
        if value is not None:
            if not isinstance(value, (self.document_type, str, dict, RecordID)):
                raise TypeError(
                    f"Expected {self.document_type.__name__}, id string, record dict, or RecordID for field '{self.name}', got {type(value)}")

            if isinstance(value, self.document_type) and value.id is None:
                raise ValueError(f"Cannot reference an unsaved {self.document_type.__name__} document")

        return value

    def to_db(self, value: Any) -> Optional[str]:
        """Convert Python reference to database representation.

        This method converts a Python reference (document instance, ID string,
        dictionary with an ID, or RecordID object) to a database representation.

        Args:
            value: The Python reference to convert

        Returns:
            The database representation of the reference

        Raises:
            ValueError: If the referenced document is not saved
        """
        if value is None:
            return None

        # If it's already a record ID string
        if isinstance(value, str):
            return value

        # If it's a RecordID object
        if isinstance(value, RecordID):
            return value

        # If it's a document instance
        if isinstance(value, self.document_type):
            if value.id is None:
                raise ValueError(f"Cannot reference an unsaved {self.document_type.__name__} document")
            return value.id

        # If it's a dict (partial reference)
        if isinstance(value, dict) and value.get('id'):
            return value['id']

        return value

    def from_db(self, value: Any, dereference: bool = False) -> Any:
        """Convert database reference to Python representation.

        This method converts a database reference to a Python representation.
        If the value is already a resolved document (from FETCH), return it as is.
        If dereference is False, it returns the string reference as is.
        If dereference is True but value is still a string, fetch the referenced document.

        Args:
            value: The database reference to convert
            dereference: Whether to dereference the reference (default: False)

        Returns:
            The Python representation of the reference
        """
        # If value is already a dict (fetched document), convert it to document instance
        if isinstance(value, dict) and 'id' in value:
            try:
                return self.document_type.from_db(value)
            except Exception:
                # If conversion fails, return the dict as is
                return value
        
        if isinstance(value, str) and ':' in value:
            # This is a record ID reference
            if dereference:
                # If dereference is True, fetch the referenced document
                # We need to use get_sync here because from_db is not async
                try:
                    return self.document_type.objects.get_sync(id=value)
                except Exception:
                    # If fetching fails, return the ID as is
                    return value
            else:
                # If dereference is False, return the ID as is
                return value
        elif isinstance(value, RecordID):
            # This is a RecordID object
            if dereference:
                # If dereference is True, fetch the referenced document
                try:
                    return self.document_type.objects.get_sync(id=str(value))
                except Exception:
                    # If fetching fails, return the RecordID as is
                    return value
            else:
                # If dereference is False, return the RecordID as is
                return value
        return value


class RelationField(Field):
    """Field representing a relation between documents.

    This field type stores relations between documents in the database.
    It can accept a document instance, an ID string, or a dictionary with an ID.

    Attributes:
        to_document: The type of document being related to
    """

    def __init__(self, to_document: Type, **kwargs: Any) -> None:
        """Initialize a new RelationField.

        Args:
            to_document: The type of document being related to
            required: Whether the field is required (default: False)
            default: Default value for the field
            db_field: Name of the field in the database (defaults to the field name)
            define_schema: Whether to define this field in the schema (even for SCHEMALESS tables)
            indexed: Whether the field should be indexed (default: False)
            unique: Whether the index should enforce uniqueness (default: False)
            search: Whether the index is a search index (default: False)
            analyzer: Analyzer to use for search indexes
            index_with: List of other field names to include in the index
        """
        self.to_document = to_document
        super().__init__(**kwargs)
        self.py_type = Union[Type, str, dict]

    def validate(self, value: Any) -> Any:
        """Validate the relation value.

        This method checks if the value is a valid relation to another document.
        It accepts a document instance, an ID string, or a dictionary with an ID.

        Args:
            value: The value to validate

        Returns:
            The validated relation value

        Raises:
            TypeError: If the value is not a valid relation
        """
        value = super().validate(value)
        if value is not None:
            if not isinstance(value, (self.to_document, str, dict, RecordID)):
                raise TypeError(
                    f"Expected {self.to_document.__name__}, id string, record dict, or RecordID for field '{self.name}', got {type(value)}")

        return value

    def to_db(self, value: Any) -> Optional[str]:
        """Convert Python relation to database representation.

        This method converts a Python relation (document instance, ID string,
        or dictionary with an ID) to a database representation.

        Args:
            value: The Python relation to convert

        Returns:
            The database representation of the relation

        Raises:
            ValueError: If the related document is not saved
        """
        if value is None:
            return None

        # If it's already a record ID string
        if isinstance(value, str):
            if ':' not in value:
                return f"{self.to_document._get_collection_name()}:{value}"
            return value

        # If it's a document instance
        if isinstance(value, self.to_document):
            if value.id is None:
                raise ValueError(f"Cannot relate to an unsaved {self.to_document.__name__} document")
            # If the ID already includes the collection name, return it as is
            if isinstance(value.id, str) and ':' in value.id:
                return value.id
            # Otherwise, add the collection name
            return f"{self.to_document._get_collection_name()}:{value.id}"

        # If it's a dict
        if isinstance(value, dict) and value.get('id'):
            id_val = value['id']
            # If the ID already includes the collection name, return it as is
            if isinstance(id_val, str) and ':' in id_val:
                return id_val
            # Otherwise, add the collection name
            return f"{self.to_document._get_collection_name()}:{id_val}"

        return value

    def from_db(self, value: Any, dereference: bool = False) -> Any:
        """Convert database relation to Python representation.

        This method converts a database relation to a Python representation.
        If the value is already a resolved document (from FETCH), return it as is.
        If dereference is False, it returns the string reference as is.
        If dereference is True but value is still a string, fetch the related document.

        Args:
            value: The database relation to convert
            dereference: Whether to dereference the relation (default: False)

        Returns:
            The Python representation of the relation
        """
        # If value is already a dict (fetched document), convert it to document instance
        if isinstance(value, dict) and 'id' in value:
            try:
                return self.to_document.from_db(value)
            except Exception:
                # If conversion fails, return the dict as is
                return value
        
        if isinstance(value, str) and ':' in value:
            # This is a record ID reference
            if dereference:
                # If dereference is True, fetch the related document
                # We need to use get_sync here because from_db is not async
                try:
                    return self.to_document.objects.get_sync(id=value)
                except Exception:
                    # If fetching fails, return the ID as is
                    return value
            else:
                # If dereference is False, return the ID as is
                return value
        elif isinstance(value, RecordID):
            # This is a RecordID object
            if dereference:
                # If dereference is True, fetch the related document
                try:
                    return self.to_document.objects.get_sync(id=str(value))
                except Exception:
                    # If fetching fails, return the RecordID as is
                    return value
            else:
                # If dereference is False, return the RecordID as is
                return value
        return value

    async def get_related_documents(self, instance: Any) -> List[Any]:
        """Get documents related through this relation field.

        This method retrieves documents related to the given instance through
        this relation field. It uses the RelationQuerySet to get related documents.

        Args:
            instance: The instance to get related documents for

        Returns:
            List of related documents

        Raises:
            ValueError: If the instance is not saved
        """
        if not instance.id:
            raise ValueError("Cannot get related documents for unsaved instance")

        # Use the RelationQuerySet to get related documents
        from ..query import RelationQuerySet
        relation_name = self.name

        # Get the default connection
        from ..connection import ConnectionRegistry
        connection = ConnectionRegistry.get_default_connection(async_mode=True)

        # Create a RelationQuerySet for the relation
        relation_queryset = RelationQuerySet(
            from_document=instance.__class__,
            relation=relation_name,
            connection=connection
        )

        # Get related documents
        return await relation_queryset.get_related(
            instance, target_document=self.to_document
        )

    def get_related_documents_sync(self, instance: Any) -> List[Any]:
        """Get documents related through this relation field synchronously.

        This method retrieves documents related to the given instance through
        this relation field. It uses the RelationQuerySet to get related documents.

        Args:
            instance: The instance to get related documents for

        Returns:
            List of related documents

        Raises:
            ValueError: If the instance is not saved
        """
        if not instance.id:
            raise ValueError("Cannot get related documents for unsaved instance")

        # Use the RelationQuerySet to get related documents
        from ..query import RelationQuerySet
        relation_name = self.name

        # Get the default connection
        from ..connection import ConnectionRegistry
        connection = ConnectionRegistry.get_default_connection(async_mode=False)

        # Create a RelationQuerySet for the relation
        relation_queryset = RelationQuerySet(
            from_document=instance.__class__,
            relation=relation_name,
            connection=connection
        )

        # Get related documents
        return relation_queryset.get_related_sync(
            instance, target_document=self.to_document
        )
