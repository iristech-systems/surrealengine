
import json
import asyncio
from .exceptions import MultipleObjectsReturned, DoesNotExist
from .connection import ConnectionRegistry
from surrealdb import RecordID

class QuerySet:
    """Query builder for SurrealDB."""

    def __init__(self, document_class, connection):
        self.document_class = document_class
        self.connection = connection
        self.query_parts = []
        self.limit_value = None
        self.start_value = None
        self.order_by_value = None

    def filter(self, **kwargs):
        """Add filter conditions."""
        for k, v in kwargs.items():
            parts = k.split('__')
            field = parts[0]

            # Handle operators
            if len(parts) > 1:
                op = parts[1]
                if op == 'gt':
                    self.query_parts.append((field, '>', v))
                elif op == 'lt':
                    self.query_parts.append((field, '<', v))
                elif op == 'gte':
                    self.query_parts.append((field, '>=', v))
                elif op == 'lte':
                    self.query_parts.append((field, '<=', v))
                elif op == 'ne':
                    self.query_parts.append((field, '!=', v))
                elif op == 'in':
                    self.query_parts.append((field, 'INSIDE', v))
                elif op == 'nin':
                    self.query_parts.append((field, 'NOT INSIDE', v))
                elif op == 'contains':
                    if isinstance(v, str):
                        self.query_parts.append((f"string::contains({field}, '{v}')", '=', True))
                    else:
                        self.query_parts.append((field, 'CONTAINS', v))
                elif op == 'startswith':
                    self.query_parts.append((f"string::startsWith({field}, '{v}')", '=', True))
                elif op == 'endswith':
                    self.query_parts.append((f"string::endsWith({field}, '{v}')", '=', True))
                elif op == 'regex':
                    self.query_parts.append((f"string::matches({field}, r'{v}')", '=', True))
                else:
                    raise ValueError(f"Unknown operator: {op}")
            else:
                # Simple equality
                self.query_parts.append((field, '=', v))

        return self

    def limit(self, value):
        """Set limit."""
        self.limit_value = value
        return self

    def start(self, value):
        """Set start (offset)."""
        self.start_value = value
        return self

    def order_by(self, field, direction='ASC'):
        """Set ordering."""
        self.order_by_value = (field, direction)
        return self

    def _build_query(self):
        query = f"SELECT * FROM {self.document_class._get_collection_name()}"

        if self.query_parts:
            conditions = []
            for field, op, value in self.query_parts:
                # Handle special cases
                if op == '=' and isinstance(field, str) and '::' in field:
                    conditions.append(f"{field}")
                else:
                    # Special handling for INSIDE and NOT INSIDE operators
                    if op in ('INSIDE', 'NOT INSIDE'):
                        value_str = json.dumps(value)
                        conditions.append(f"{field} {op} {value_str}")
                    else:
                        conditions.append(f"{field} {op} {json.dumps(value)}")

            query += f" WHERE {' AND '.join(conditions)}"
        return query

    async def all(self):
        """Execute the query and return all results."""
        query = self._build_query()
        results = await self.connection.client.query(query)

        if not results or not results[0]:
            return []

        # Create one instance per result document
        processed_results = [self.document_class.from_db(doc) for doc in results]
        return processed_results

    async def first(self):
        """Execute the query and return the first result."""
        self.limit_value = 1
        results = await self.all()
        return results[0] if results else None

    async def count(self):
        """Count documents."""
        count_query = f"SELECT count() FROM {self.document_class._get_collection_name()}"

        if self.query_parts:
            conditions = []
            for field, op, value in self.query_parts:
                # Handle special cases
                if op == '=' and isinstance(field, str) and '::' in field:
                    conditions.append(f"{field}")
                else:
                    # Special handling for INSIDE and NOT INSIDE operators
                    if op in ('INSIDE', 'NOT INSIDE'):
                        value_str = json.dumps(value)
                        conditions.append(f"{field} {op} {value_str}")
                    else:
                        conditions.append(f"{field} {op} {json.dumps(value)}")

            count_query += f" WHERE {' AND '.join(conditions)}"

        result = await self.connection.client.query(count_query)

        if not result or not result[0]:
            return 0

        return result[0][0]['count']

    async def get(self, **kwargs):
        """Get a single document matching the query."""
        self.filter(**kwargs)
        self.limit_value = 2  # Get 2 to check for multiple
        results = await self.all()

        if not results:
            raise DoesNotExist(f"{self.document_class.__name__} matching query does not exist.")
        if len(results) > 1:
            raise MultipleObjectsReturned(f"Multiple {self.document_class.__name__} objects returned instead of one")

        return results[0]

    async def create(self, **kwargs):
        """Create a new document."""
        document = self.document_class(**kwargs)
        return await document.save(self.connection)

    async def update(self, **kwargs):
        """Update documents matching the query."""
        update_query = f"UPDATE {self.document_class._get_collection_name()}"

        if self.query_parts:
            conditions = []
            for field, op, value in self.query_parts:
                # Handle special cases
                if op == '=' and isinstance(field, str) and '::' in field:
                    conditions.append(f"{field}")
                else:
                    # Special handling for INSIDE and NOT INSIDE operators
                    if op in ('INSIDE', 'NOT INSIDE'):
                        value_str = json.dumps(value)
                        conditions.append(f"{field} {op} {value_str}")
                    else:
                        conditions.append(f"{field} {op} {json.dumps(value)}")

            update_query += f" WHERE {' AND '.join(conditions)}"

        update_query += f" SET {', '.join(f'{k} = {json.dumps(v)}' for k, v in kwargs.items())}"

        result = await self.connection.client.query(update_query)

        if not result or not result[0]:
            return []

        return [self.document_class.from_db(doc) for doc in result[0]]

    async def delete(self):
        """Delete documents matching the query."""
        delete_query = f"DELETE FROM {self.document_class._get_collection_name()}"

        if self.query_parts:
            conditions = []
            for field, op, value in self.query_parts:
                # Handle special cases
                if op == '=' and isinstance(field, str) and '::' in field:
                    conditions.append(f"{field}")
                else:
                    # Special handling for INSIDE and NOT INSIDE operators
                    if op in ('INSIDE', 'NOT INSIDE'):
                        value_str = json.dumps(value)
                        conditions.append(f"{field} {op} {value_str}")
                    else:
                        conditions.append(f"{field} {op} {json.dumps(value)}")

            delete_query += f" WHERE {' AND '.join(conditions)}"

        result = await self.connection.client.query(delete_query)

        if not result or not result[0]:
            return 0

        return len(result[0])

    async def bulk_create(self, documents, batch_size=1000, validate=True, return_documents=True):
        """Create multiple documents in a single operation.

        Args:
            documents: List of Document instances to create
            batch_size: Number of documents per batch (default: 1000)
            validate: Whether to validate documents (default: True)
            return_documents: Whether to return created documents (default: True)

        Returns:
            List of created documents with their IDs set if return_documents=True,
            otherwise returns the count of created documents
        """
        if not documents:
            return [] if return_documents else 0

        collection = self.document_class._get_collection_name()
        total_created = 0
        created_docs = [] if return_documents else None

        # Process in batches
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]

            # Validate batch if required
            if validate:
                # Parallel validation using asyncio.gather
                validation_tasks = [doc.validate() for doc in batch]
                await asyncio.gather(*validation_tasks)

            # Convert batch to DB representation
            data = [doc.to_db() for doc in batch]

            # Construct optimized bulk insert query
            query = f"INSERT INTO {collection} {json.dumps(data)};"

            # Execute batch insert
            try:
                result = await self.connection.client.query(query)

                if return_documents and result and result[0]:
                    # Process results if needed
                    batch_docs = [self.document_class.from_db(doc_data)
                                  for doc_data in result[0]]
                    created_docs.extend(batch_docs)
                    total_created += len(batch_docs)
                elif result and result[0]:
                    total_created += len(result[0])

            except Exception as e:
                # Log error and continue with next batch
                print(f"Error in bulk create batch: {str(e)}")
                continue

        return created_docs if return_documents else total_created



class RelationQuerySet:
    """Query set specifically for graph relations."""

    def __init__(self, from_document, connection, relation=None):
        self.from_document = from_document
        self.connection = connection
        self.relation = relation
        self.query_parts = []

    async def relate(self, from_instance, to_instance, **attrs):
        """Create a relation between two instances."""
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
            attrs_str = ", ".join([f"{k}: {json.dumps(v)}" for k, v in attrs.items()])
            query += f" CONTENT {{ {attrs_str} }}"

        result = await self.connection.client.query(query)

        # Return the relation record
        if result and result[0]:
            return result[0]

        return None

    async def get_related(self, instance, target_document=None, **filters):
        """Get related documents."""
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
            query = f"SELECT ->{relation}->* FROM {from_id}"
        else:
            # When we just want the relations
            query = f"SELECT id, ->{relation}->? as related FROM {from_id}"

        # Add additional filters if provided
        if filters:
            conditions = []
            for field, value in filters.items():
                conditions.append(f"{field} = {json.dumps(value)}")
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

    async def update_relation(self, from_instance, to_instance, **attrs):
        """Update an existing relation."""
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
        relation_query = f"SELECT id FROM {relation} WHERE in = {json.dumps(from_id)} AND out = {json.dumps(to_id)}"
        relation_result = await self.connection.client.query(relation_query)

        if not relation_result or not relation_result[0]:
            return await self.relate(from_instance, to_instance, **attrs)

        # Get relation ID and update
        relation_id = relation_result[0][0]['id']
        update_query = f"UPDATE {relation_id} SET"

        # Add attributes
        updates = []
        for key, value in attrs.items():
            updates.append(f" {key} = {json.dumps(value)}")

        update_query += ",".join(updates)

        result = await self.connection.client.query(update_query)

        if result and result[0]:
            return result[0][0]

        return None

    async def delete_relation(self, from_instance, to_instance=None):
        """Delete a relation."""
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
            query = f"DELETE FROM {relation} WHERE in = {json.dumps(from_id)} AND out = {json.dumps(to_id)}"
        else:
            # Delete all relations from this instance
            query = f"DELETE FROM {relation} WHERE in = {json.dumps(from_id)}"

        result = await self.connection.client.query(query)

        if result and result[0]:
            return len(result[0])

        return 0


class QuerySetDescriptor:
    """Descriptor that provides QuerySet access through Document.objects"""

    def __init__(self):
        self.owner = None
        self.connection = None

    def __get__(self, obj, owner):
        self.owner = owner
        self.connection = ConnectionRegistry.get_default_connection()
        return self

    async def __call__(self, **kwargs):
        """Allow direct filtering through call syntax."""
        queryset = QuerySet(self.owner, self.connection)
        # Apply filters and return results
        return await queryset.filter(**kwargs).all()

    async def get(self, **kwargs):
        """Allow direct get operation."""
        queryset = QuerySet(self.owner, self.connection)
        return await queryset.get(**kwargs)

    def filter(self, **kwargs):
        """Create a QuerySet with filters."""
        queryset = QuerySet(self.owner, self.connection)
        return queryset.filter(**kwargs)