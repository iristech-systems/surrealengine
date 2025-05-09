import json
from .exceptions import DoesNotExist, MultipleObjectsReturned
from surrealdb import RecordID

class SchemalessQuerySet:
    """QuerySet for schemaless operations"""

    def __init__(self, table_name, connection):
        self.table_name = table_name
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

    async def all(self):
        """Execute the query and return all results."""
        query = self._build_query()
        results = await self.connection.client.query(query)
        print(f"SchemalessQuerySet query: {query}")
        print(f"SchemalessQuerySet raw results: {results}")

        if not results or not results[0]:
            return []

        # If we have a document class in the connection's database mapping, use it
        from .document import Document  # Import at the top of the file
        doc_class = None

        # Find matching document class
        for cls in Document.__subclasses__():
            if hasattr(cls, '_meta') and cls._meta.get('collection') == self.table_name:
                doc_class = cls
                break

        # Process results based on whether we found a matching document class
        processed_results = []
        if doc_class:
            for doc_data in results:  # results[0] contains the actual data
                instance = doc_class.from_db(doc_data)
                processed_results.append(instance)
        else:
            # If no matching document class, create dynamic objects
            from types import SimpleNamespace
            for doc_data in results:
                # Check if doc_data is a dictionary, if not try to convert or skip
                if isinstance(doc_data, dict):
                    instance = SimpleNamespace(**doc_data)
                else:
                    # If it's a string, try to use it as a name attribute
                    instance = SimpleNamespace(name=str(doc_data))
                processed_results.append(instance)

        print(f"SchemalessQuerySet processed results: {processed_results}")
        print(f"SchemalessQuerySet length: {len(processed_results)}")
        return processed_results

    def __await__(self):
        """Make the queryset awaitable."""
        return self.all().__await__()


    async def get(self, **kwargs):
        # Special handling for ID-based lookup
        if len(kwargs) == 1 and 'id' in kwargs:
            id_value = kwargs['id']
            # Handle both full and short ID formats
            if ':' in str(id_value):
                record_id = id_value.split(':')[1]
            else:
                record_id = id_value

            # Use direct select with RecordID
            result = await self.connection.client.select(RecordID(self.table_name, record_id))
            if not result or result == self.table_name:  # Check for the table name response
                raise DoesNotExist(f"Object in table '{self.table_name}' matching query does not exist.")

            # Handle the result appropriately
            if isinstance(result, list):
                return result[0] if result else None
            return result

        # Rest of the method remains the same...

    def _build_query(self):
        query = f"SELECT * FROM {self.table_name}"

        if self.query_parts:
            conditions = []
            for field, op, value in self.query_parts:
                if field == 'id' and isinstance(value, str):
                    # Handle record IDs specially
                    if ':' in value:
                        # Full record ID format (table:id)
                        conditions.append(f"id = {json.dumps(value)}")
                    else:
                        # Short ID format (just id)
                        conditions.append(f"id = {json.dumps(f'{self.table_name}:{value}')}")
                elif op == '=' and isinstance(field, str) and '::' in field:
                    conditions.append(f"{field}")
                else:
                    if op in ('INSIDE', 'NOT INSIDE'):
                        value_str = json.dumps(value)
                        conditions.append(f"{field} {op} {value_str}")
                    else:
                        conditions.append(f"{field} {op} {json.dumps(value)}")

            query += f" WHERE {' AND '.join(conditions)}"
        return query


class SchemalessTable:
    """Dynamic table accessor"""

    def __init__(self, name, connection):
        self.name = name
        self.connection = connection

    @property
    def objects(self):
        return SchemalessQuerySet(self.name, self.connection)

    async def __call__(self, **kwargs):
        queryset = SchemalessQuerySet(self.name, self.connection)
        results = await queryset.filter(**kwargs).all()

        # Convert results to SimpleNamespace objects if they aren't already Document instances
        if results and not hasattr(results[0], '_data'):  # Check if it's not a Document instance
            from types import SimpleNamespace
            results = [SimpleNamespace(**result) if isinstance(result, dict) else result
                       for result in results]

        return results


class SurrealEngine:
    """Dynamic database accessor"""

    def __init__(self, connection):
        self.connection = connection

    def __getattr__(self, name):
        return SchemalessTable(name, self.connection)