from typing import Any, Dict, List, Optional, Tuple, Union, TypeVar
from .exceptions import MultipleObjectsReturned, DoesNotExist
from surrealdb import RecordID
from .pagination import PaginationResult
from .record_id_utils import RecordIdUtils
from .surrealql import escape_literal

T = TypeVar("T", bound="BaseQuerySet")

_ALLOWED_VECTOR_METRICS = {
    "COSINE",
    "EUCLIDEAN",
    "MANHATTAN",
    "MINKOWSKI",
    "HAMMING",
    "CHEBYSHEV",
}


# Import these at runtime to avoid circular imports
def _get_connection_classes():
    from .connection import SurrealEngineAsyncConnection, SurrealEngineSyncConnection

    return SurrealEngineAsyncConnection, SurrealEngineSyncConnection


class BaseQuerySet:
    """Base query builder for SurrealDB.

    This class provides the foundation for building queries in SurrealDB.
    It includes methods for filtering, limiting, ordering, and retrieving results.
    Subclasses must implement specific methods like _build_query, all, and count.

    Attributes:
        connection: The database connection to use for queries
        query_parts: List of query conditions (field, operator, value)
        limit_value: Maximum number of results to return
        start_value: Number of results to skip (for pagination)
        order_by_value: Field and direction to order results by
        group_by_fields: Fields to group results by
        split_fields: Fields to split results by
        fetch_fields: Fields to fetch related records for
        with_index: Index to use for the query
    """

    def __init__(self, connection: Any) -> None:
        """Initialize a new BaseQuerySet.

        Args:
            connection: The database connection to use for queries
        """
        self.connection = connection
        self.query_parts: List[Tuple[str, str, Any]] = []
        self.limit_value: Optional[int] = None
        self.start_value: Optional[int] = None
        self.order_by_value: Optional[Tuple[str, str]] = None
        self.group_by_fields: List[str] = []
        self.split_fields: List[str] = []
        self.fetch_fields: List[str] = []
        self._with_index: Optional[str] = None
        self.select_fields: Optional[List[str]] = None
        self.omit_fields: List[str] = []
        self.timeout_value: Optional[str] = None
        self.tempfiles_value: bool = False
        self.explain_value: bool = False
        self.explain_full_value: bool = False
        self.group_by_all: bool = False
        # Graph traversal state
        self._traversal_path: Optional[str] = None
        self._traversal_unique: bool = True
        self._traversal_max_depth: Optional[int] = None
        # Performance optimization attributes
        self._bulk_id_selection: Optional[List[Any]] = None
        self._id_range_selection: Optional[Tuple[Any, Any, bool]] = None
        self._prefer_direct_access: bool = False

    def is_async_connection(self) -> bool:
        """Check if the connection is asynchronous.

        Returns:
            True if the connection is asynchronous, False otherwise
        """
        SurrealEngineAsyncConnection, SurrealEngineSyncConnection = (
            _get_connection_classes()
        )
        return isinstance(self.connection, SurrealEngineAsyncConnection)

    def filter(self: T, query=None, **kwargs) -> T:
        """Add filter conditions to the query with automatic ID optimization.

        # ... (implementation same)
        """
        # Clone first to avoid mutating the original queryset
        result = self if (query is None and not kwargs) else self._clone()
        if query:
            # Handle QueryExpression
            if hasattr(query, "apply_to_queryset"):
                result = query.apply_to_queryset(result)
            # Handle Q object
            elif hasattr(query, "to_conditions"):
                conditions = query.to_conditions()
                if conditions:
                    result.query_parts.extend(conditions)
                else:
                    # Fallback to raw WHERE clause for complex queries
                    where_clause = query.to_where_clause()
                    if where_clause:
                        result.query_parts.append(("__raw__", "=", where_clause))

        # Handle kwargs
        for key, value in kwargs.items():
            # Check for subqueries (if value is a QuerySet)
            if hasattr(value, "_build_query"):
                # Compile the QuerySet into a subquery string
                compiled_subquery = value._build_query()
                # Wrap the subquery in parentheses for SurrealQL
                subquery_str = f"({compiled_subquery})"

                if "__" in key:
                    parts = key.split("__")
                    field_name = parts[0]
                    operator = parts[1]

                    op_map = {
                        "in": "IN",
                        "nin": "NOT IN",
                        "eq": "=",
                        "ne": "!=",
                    }
                    op = op_map.get(operator, "=")

                    # Store as a raw condition to avoid parameterization on the subquery itself
                    result.query_parts.append(
                        ("__raw__", "=", f"{field_name} {op} {subquery_str}")
                    )
                else:
                    # Default to exactly equal to the subquery result
                    result.query_parts.append(
                        ("__raw__", "=", f"{key} = {subquery_str}")
                    )
            else:
                if "__" in key:
                    parts = key.split("__")
                    field_name = parts[0]
                    operator = parts[1]

                    # Map operators
                    op_map = {
                        "gt": ">",
                        "lt": "<",
                        "gte": ">=",
                        "lte": "<=",
                        "ne": "!=",
                        "in": "IN",
                        "nin": "NOT IN",
                        "contains": "CONTAINS",
                        "startswith": "STARTSWITH",
                        "endswith": "ENDSWITH",
                        "regex": "REGEX",
                        "search": "SEARCH",
                        "match": "SEARCH",
                        "knn": "KNN",
                    }
                    op = op_map.get(operator, "=")
                    result.query_parts.append((field_name, op, value))
                else:
                    result.query_parts.append((key, "=", value))

        return result

    def search(self: T, text: str, *fields: Union[str, Any]) -> T:
        """Perform a full-text search using the @@ operator.

        Args:
            text: The text to search for
            *fields: Optional. Specific fields to search in. Can be field names or Field instances.
        Returns:
            A cloned QuerySet with the search condition
        """
        clone = self._clone()

        if fields:
            # Extract names if they are Field instances
            field_names = [f.name if hasattr(f, "name") else str(f) for f in fields]

            # If multiple fields, we use an OR group, typically mapping to index fields
            if len(field_names) == 1:
                clone.query_parts.append(
                    ("__raw__", "=", f"{field_names[0]} @@ {escape_literal(text)}")
                )
            else:
                parts = [f"{f} @@ {escape_literal(text)}" for f in field_names]
                group = " OR ".join(parts)
                clone.query_parts.append(("__raw__", "=", f"({group})"))
        else:
            # Basic fallback to search against a generic text field or similar
            # Often useful when `with_index` is used
            clone.query_parts.append(
                ("__raw__", "=", f"text @@ {escape_literal(text)}")
            )

        return clone

    def semantic_search(
        self: T,
        field: Union[str, Any],
        vector: Any,
        k: int = 10,
        metric: Optional[str] = None,
    ) -> T:
        """Perform semantic vector search using SurrealQL KNN syntax.

        The generated condition follows SurrealQL's documented KNN operator form:
        `field <|K,DISTANCE_METRIC|> [vector...]`.

        Args:
            field: Vector field name (or Field instance)
            vector: Query embedding/vector
            k: Number of nearest neighbors to retrieve
            metric: Optional distance metric. If omitted, inferred from Meta.indexes.

        Returns:
            A cloned QuerySet with a vector KNN condition.
        """
        clone = self._clone()
        field_name = field.name if hasattr(field, "name") else str(field)
        payload = {
            "vector": vector,
            "k": k,
            "metric": metric,
        }
        clone.query_parts.append((field_name, "KNN", payload))
        return clone

    def _normalize_vector_metric(self, metric: str) -> str:
        """Normalize and validate vector distance metric names."""
        normalized = str(metric).strip().upper()
        if normalized not in _ALLOWED_VECTOR_METRICS:
            allowed = ", ".join(sorted(_ALLOWED_VECTOR_METRICS))
            raise ValueError(
                f"Unsupported vector distance metric '{metric}'. "
                f"Allowed values: {allowed}."
            )
        return normalized

    def _validate_vector_dimension(self, field_name: str, vector_value: Any) -> None:
        """Validate query vector length against VectorField dimension when available."""
        document_class = getattr(self, "document_class", None)
        if not document_class or not hasattr(document_class, "_fields"):
            return

        field_obj = document_class._fields.get(field_name)
        expected_dim = getattr(field_obj, "dimension", None)
        if expected_dim is None:
            return

        if not isinstance(vector_value, (list, tuple)):
            raise ValueError(
                f"Vector value for field '{field_name}' must be a list/tuple, "
                f"got {type(vector_value).__name__}."
            )

        if len(vector_value) != expected_dim:
            raise ValueError(
                f"Vector dimension mismatch for field '{field_name}'. "
                f"Expected {expected_dim}, got {len(vector_value)}."
            )

    def _infer_vector_metric(
        self, field_name: str, explicit_metric: Optional[str]
    ) -> str:
        """Infer metric from Meta.indexes when not provided explicitly.

        Precedence:
        1) explicit metric argument
        2) single unique dist from vector index metadata for the field
        3) raise clear validation error
        """
        if explicit_metric is not None:
            return self._normalize_vector_metric(explicit_metric)

        document_class = getattr(self, "document_class", None)
        if not document_class or not hasattr(document_class, "_meta"):
            raise ValueError(
                f"Unable to infer vector metric for field '{field_name}'; "
                "provide metric explicitly."
            )

        indexes = (document_class._meta or {}).get("indexes", []) or []
        inferred_metrics: List[str] = []
        for index in indexes:
            if not isinstance(index, dict):
                continue
            if not index.get("dimension"):
                continue
            fields = index.get("fields", []) or []
            if field_name not in fields:
                continue
            dist = index.get("dist")
            if dist:
                inferred_metrics.append(self._normalize_vector_metric(dist))

        unique_metrics = sorted(set(inferred_metrics))
        if len(unique_metrics) == 1:
            return unique_metrics[0]

        if len(unique_metrics) > 1:
            raise ValueError(
                f"Ambiguous vector metric for field '{field_name}'. "
                f"Found multiple metrics in index metadata: {', '.join(unique_metrics)}. "
                "Provide metric explicitly."
            )

        raise ValueError(
            f"Unable to infer vector metric for field '{field_name}' from index metadata; "
            "provide metric explicitly."
        )

    def _normalize_knn_payload(
        self, field_name: str, value: Any
    ) -> Tuple[List[float], int, str]:
        """Normalize KNN payload into (vector, k, metric)."""
        vector_value: Any
        k_value: Any
        metric_value: Optional[str]

        if isinstance(value, dict):
            if "vector" not in value or "k" not in value:
                raise ValueError(
                    f"KNN value for field '{field_name}' must include 'vector' and 'k'."
                )
            vector_value = value.get("vector")
            k_value = value.get("k")
            metric_value = value.get("metric")
        elif isinstance(value, (tuple, list)):
            if len(value) == 2:
                vector_value, k_value = value
                metric_value = None
            elif len(value) == 3:
                vector_value, k_value, metric_value = value
            else:
                raise ValueError(
                    f"KNN tuple/list for field '{field_name}' must be (vector, k) "
                    "or (vector, k, metric)."
                )
        else:
            raise ValueError(
                f"KNN value for field '{field_name}' must be dict, tuple, or list."
            )

        if hasattr(vector_value, "tolist"):
            vector_value = vector_value.tolist()

        if not isinstance(k_value, int) or k_value <= 0:
            raise ValueError(
                f"KNN 'k' for field '{field_name}' must be a positive integer."
            )

        converted_vector = self._convert_value_for_query(field_name, vector_value)
        if hasattr(converted_vector, "tolist"):
            converted_vector = converted_vector.tolist()

        if not isinstance(converted_vector, (list, tuple)):
            raise ValueError(
                f"KNN vector for field '{field_name}' must be list/tuple-like."
            )

        vector_list = [float(v) for v in converted_vector]
        self._validate_vector_dimension(field_name, vector_list)
        metric = self._infer_vector_metric(field_name, metric_value)
        return vector_list, k_value, metric

    def only(self: T, *fields: str) -> T:
        """Select only the specified fields.
        # ...
        """
        clone = self._clone()
        select_fields = list(fields)
        if "id" not in select_fields:
            select_fields.append("id")
        clone.select_fields = select_fields
        return clone

    def omit(self: T, *fields: str) -> T:
        """Exclude specific fields from the results.
        # ...
        """
        clone = self._clone()
        clone.omit_fields.extend(fields)
        return clone

    def limit(self: T, value: int) -> T:
        """Set the maximum number of results to return.
        # ...
        """
        self.limit_value = value
        return self

    def start(self: T, value: int) -> T:
        """Set the number of results to skip (for pagination).
        # ...
        """
        self.start_value = value
        return self

    def order_by(self: T, field: str, direction: str = "ASC") -> T:
        """Set the field and direction to order results by.
        # ...
        """
        self.order_by_value = (field, direction)
        return self

    def group_by(self: T, *fields: str, all: bool = False) -> T:
        """Group the results by the specified fields or group all.
        # ...
        """
        self.group_by_fields.extend(fields)
        self.group_by_all = all
        return self

    def split(self: T, *fields: str) -> T:
        """Split the results by the specified fields.
        # ...
        """
        self.split_fields.extend(fields)
        return self

    def fetch(self: T, *fields: str) -> T:
        """Fetch related records for the specified fields.
        # ...
        """
        self.fetch_fields.extend(fields)
        return self

    def get_many(self: T, ids: List[Union[str, Any]]) -> T:
        """Get multiple records by IDs using optimized direct record access.
        # ...
        """
        clone = self._clone()
        clone._bulk_id_selection = ids
        return clone

    def get_range(
        self: T,
        start_id: Union[str, Any],
        end_id: Union[str, Any],
        inclusive: bool = True,
    ) -> T:
        """Get a range of records by ID using optimized range syntax.
        # ...
        """
        clone = self._clone()
        clone._id_range_selection = (start_id, end_id, inclusive)
        return clone

    def with_index(self: T, index: str) -> T:
        """Use the specified index for the query.
        # ...
        """
        self._with_index = index
        return self

    def no_index(self: T) -> T:
        """Do not use any index for the query.
        # ...
        """
        self._with_index = "NOINDEX"
        return self

    def timeout(self: T, duration: str) -> T:
        """Set a timeout for the query execution.
        # ...
        """
        self.timeout_value = duration
        return self

    def tempfiles(self: T, value: bool = True) -> T:
        """Enable or disable using temporary files for large queries.
        # ...
        """
        self.tempfiles_value = value
        return self

    def with_explain(self: T, full: bool = False) -> T:
        """Explain the query execution plan (builder pattern).
        # ...
        """
        self.explain_value = True
        self.explain_full_value = full
        return self

    def use_direct_access(self: T) -> T:
        """Mark this queryset to prefer direct record access when possible.
        # ...
        """
        clone = self._clone()
        clone._prefer_direct_access = True
        return clone

    def _build_query(self) -> str:
        """Build the base query string.

        This method must be implemented by subclasses to generate the appropriate
        query string for the specific database operation.

        Returns:
            The query string

        Raises:
            NotImplementedError: If not implemented by a subclass
        """
        raise NotImplementedError("Subclasses must implement _build_query")

    def _build_conditions(self) -> List[str]:
        """Build query conditions from query_parts.

        This method converts the query_parts list into a list of condition strings
        that can be used in a WHERE clause.

        Returns:
            List of condition strings
        """
        conditions = []
        for field, op, value in self.query_parts:
            # Handle raw query conditions
            if field == "__raw__":
                conditions.append(value)
            # Handle special cases
            elif op == "=" and isinstance(field, str) and "::" in field:
                conditions.append(f"{field}")
            else:
                # Determine if field is a RecordID field
                def _field_is_record_id(field_name: str) -> bool:
                    document_class = getattr(self, "document_class", None)
                    if not document_class or not hasattr(document_class, "_fields"):
                        return False
                    field_obj = document_class._fields.get(field_name)
                    try:
                        from .fields.id import RecordIDField  # type: ignore

                        return isinstance(field_obj, RecordIDField)
                    except Exception:
                        return False

                # Special handling for RecordIDs - only for id or RecordIDField or RecordID object
                if (
                    field == "id"
                    or _field_is_record_id(field)
                    or isinstance(value, RecordID)
                ):
                    # Ensure RecordID is properly formatted
                    if isinstance(value, str) and RecordIdUtils.is_valid_record_id(
                        value
                    ):
                        conditions.append(f"{field} {op} {value}")
                    elif isinstance(value, RecordID):
                        conditions.append(f"{field} {op} {str(value)}")
                    else:
                        # Try to normalize the RecordID
                        table_name = None
                        if hasattr(self, "document_class") and self.document_class:
                            table_name = self.document_class._get_collection_name()
                        normalized = RecordIdUtils.normalize_record_id(
                            value, table_name
                        )
                        if normalized and RecordIdUtils.is_valid_record_id(normalized):
                            conditions.append(f"{field} {op} {normalized}")
                        else:
                            conditions.append(f"{field} {op} {escape_literal(value)}")
                # Special handling for IN and NOT IN operators
                elif op in ("IN", "NOT IN"):
                    # Only treat list items as record IDs if the field is a RecordID field
                    treat_items_as_ids = _field_is_record_id(field)

                    def _is_record_id_str(s):
                        return isinstance(s, str) and RecordIdUtils.is_valid_record_id(
                            s
                        )

                    def _format_literal(item):
                        # Accept dicts with 'id'
                        if (
                            isinstance(item, dict)
                            and "id" in item
                            and _is_record_id_str(item["id"])
                            and treat_items_as_ids
                        ):
                            return item["id"]
                        # RecordID object
                        if isinstance(item, RecordID) and treat_items_as_ids:
                            return str(item)
                        # String record id
                        if _is_record_id_str(item) and treat_items_as_ids:
                            return item
                        # Fallback to escape_literal for proper quoting/escaping
                        return escape_literal(item)

                    if isinstance(value, (list, tuple, set)):
                        items = ", ".join(_format_literal(v) for v in value)
                        value_str = f"[{items}]"
                    else:
                        # Single non-iterable value - still format appropriately
                        value_str = _format_literal(value)
                    conditions.append(f"{field} {op} {value_str}")
                elif isinstance(value, RecordID):
                    # If value is a RecordID object but field is not RecordID-typed, quote it to be safe
                    conditions.append(f"{field} {op} {escape_literal(str(value))}")
                elif op == "STARTSWITH":
                    conditions.append(
                        f"string::starts_with({field}, {escape_literal(value)})"
                    )
                elif op == "ENDSWITH":
                    conditions.append(
                        f"string::ends_with({field}, {escape_literal(value)})"
                    )
                elif op == "CONTAINS":
                    if isinstance(value, str):
                        conditions.append(
                            f"string::contains({field}, {escape_literal(value)})"
                        )
                    else:
                        conditions.append(f"{field} CONTAINS {escape_literal(value)}")
                elif op in (
                    "CONTAINSANY",
                    "CONTAINSALL",
                    "CONTAINSNONE",
                    "ALLINSIDE",
                    "ANYINSIDE",
                    "NONEINSIDE",
                ):
                    # Handle new set operators
                    conditions.append(f"{field} {op} {escape_literal(value)}")
                elif op == "SEARCH":
                    conditions.append(f"{field} @@ {escape_literal(value)}")
                elif op == "KNN":
                    vector_list, k_value, metric = self._normalize_knn_payload(
                        field, value
                    )
                    conditions.append(
                        f"{field} <|{k_value},{metric}|> {escape_literal(vector_list)}"
                    )
                # Special handling for URL values
                elif isinstance(value, dict) and "__url_value__" in value:
                    # Extract the URL value and ensure it's properly quoted
                    url_value = value["__url_value__"]
                    conditions.append(f"{field} {op} {escape_literal(url_value)}")
                else:
                    # Convert value to database format if we have field information
                    db_value = self._convert_value_for_query(field, value)
                    # Always use escape_literal to ensure proper escaping of all values
                    # This is especially important for URLs, strings with special characters, Expr vars, and RecordIDs
                    conditions.append(f"{field} {op} {escape_literal(db_value)}")
        return conditions

    def _convert_value_for_query(self, field_name: str, value: Any) -> Any:
        """Convert a value to its database representation for query conditions.

        This method checks if the document class has a field definition for the given
        field name and uses its to_db() method to convert the value properly.

        Args:
            field_name: The name of the field
            value: The value to convert

        Returns:
            The converted value ready for JSON serialization
        """
        # Check if we have a document class with field definitions
        document_class = getattr(self, "document_class", None)
        if document_class and hasattr(document_class, "_fields"):
            # Get the field definition
            field_obj = document_class._fields.get(field_name)
            if field_obj and hasattr(field_obj, "to_db"):
                # Use the field's to_db method to convert the value
                try:
                    return field_obj.to_db(value)
                except Exception:
                    # If conversion fails, return the original value
                    pass

        # If no field definition or conversion failed, return original value
        return value

    def _format_record_id(self, id_value: Any) -> str:
        """Format an ID value into a proper SurrealDB record ID.

        This method handles various RecordID formats including URL-encoded versions.

        Args:
            id_value: The ID value to format

        Returns:
            Properly formatted record ID string
        """
        # Get table name if available
        table_name = None
        if hasattr(self, "document_class") and self.document_class:
            table_name = self.document_class._get_collection_name()

        # Use RecordIdUtils for comprehensive handling
        normalized = RecordIdUtils.normalize_record_id(id_value, table_name)

        # If normalization succeeded, return it
        if normalized is not None:
            return normalized

        # Fall back to original behavior if normalization fails
        if isinstance(id_value, str) and ":" in id_value:
            return id_value
        elif isinstance(id_value, RecordID):
            return str(id_value)
        elif table_name:
            return f"{table_name}:{id_value}"
        else:
            return str(id_value)

    def _build_direct_record_query(self) -> Optional[str]:
        """Build optimized direct record access query if applicable.

        Returns:
            Optimized query string or None if not applicable
        """
        # Handle bulk ID selection optimization
        if self._bulk_id_selection:
            if not self._bulk_id_selection:  # Empty list
                return None

            record_ids = [
                self._format_record_id(id_val) for id_val in self._bulk_id_selection
            ]
            query = f"SELECT * FROM {', '.join(record_ids)}"

            # Add other clauses (but skip WHERE since we're using direct access)
            clauses = self._build_clauses()
            for clause_name, clause_sql in clauses.items():
                if clause_name != "WHERE":  # Skip WHERE for direct access
                    query += f" {clause_sql}"

            return query

        # Handle ID range selection optimization
        if self._id_range_selection:
            start_id, end_id, inclusive = self._id_range_selection

            # Format record IDs to validate/normalize them (even if variables are unused, we validate here)
            self._format_record_id(start_id)
            self._format_record_id(end_id)

            # Extract just the numeric part for range syntax
            collection_name = getattr(self, "document_class", None)
            if collection_name:
                collection_name = collection_name._get_collection_name()

                # Extract numeric IDs from record IDs
                start_num = (
                    str(start_id).split(":")[-1]
                    if ":" in str(start_id)
                    else str(start_id)
                )
                end_num = (
                    str(end_id).split(":")[-1] if ":" in str(end_id) else str(end_id)
                )

                range_op = "..=" if inclusive else ".."
                query = (
                    f"SELECT * FROM {collection_name}:{start_num}{range_op}{end_num}"
                )
            else:
                # Fall back to WHERE clause if we can't determine collection
                return None

            # Add other clauses (but skip WHERE since we're using direct access)
            clauses = self._build_clauses()
            for clause_name, clause_sql in clauses.items():
                if clause_name != "WHERE":  # Skip WHERE for direct access
                    query += f" {clause_sql}"

            return query

        return None

    def _build_clauses(self) -> Dict[str, str]:
        """Build query clauses from the query parameters.

        This method builds the various clauses for the query string, including
        WHERE, GROUP BY, SPLIT, WITH, ORDER BY, LIMIT, START, and FETCH.

        Returns:
            Dictionary of clause names and their string representations
        """
        clauses = {}

        # Build WHERE clause
        if self.query_parts:
            conditions = self._build_conditions()
            clauses["WHERE"] = f"WHERE {' AND '.join(conditions)}"

        if self.group_by_fields:
            clauses["GROUP BY"] = f"GROUP BY {', '.join(self.group_by_fields)}"
        elif self.group_by_all:
            clauses["GROUP BY"] = "GROUP ALL"

        # Build SPLIT clause
        if self.split_fields:
            clauses["SPLIT"] = f"SPLIT {', '.join(self.split_fields)}"

        # Build WITH clause
        if self._with_index:
            clauses["WITH"] = f"WITH INDEX {self._with_index}"

        # Build ORDER BY clause
        if self.order_by_value:
            field, direction = self.order_by_value
            clauses["ORDER BY"] = f"ORDER BY {field} {direction}"

        # Build LIMIT clause
        if self.limit_value is not None:
            clauses["LIMIT"] = f"LIMIT {self.limit_value}"

        # Build START clause
        if self.start_value is not None:
            clauses["START"] = f"START {self.start_value}"

        # IMPORTANT: In SurrealQL, FETCH must be the last clause
        if self.fetch_fields:
            clauses["FETCH"] = f"FETCH {', '.join(self.fetch_fields)}"

        # Build TIMEOUT clause
        if self.timeout_value:
            clauses["TIMEOUT"] = f"TIMEOUT {self.timeout_value}"

        # Build TEMPFILES clause
        if self.tempfiles_value:
            clauses["TEMPFILES"] = "TEMPFILES"

        # Build EXPLAIN clause
        if self.explain_value:
            if self.explain_full_value:
                clauses["EXPLAIN"] = "EXPLAIN FULL"
            else:
                clauses["EXPLAIN"] = "EXPLAIN"

        return clauses

    def _get_collection_name(self) -> Optional[str]:
        """Get the collection name for this queryset.

        Returns:
            Collection name or None if not available
        """
        document_class = getattr(self, "document_class", None)
        if document_class and hasattr(document_class, "_get_collection_name"):
            return document_class._get_collection_name()
        return getattr(self, "table_name", None)

    def all(self, **kwargs: Any) -> Union[List[Any], Any]:
        """Execute the query and return all results.

        Polyglot method: executes synchronously if the connection is synchronous,
        otherwise returns an awaitable.

        Args:
            **kwargs: Additional arguments (e.g. dereference)

        Returns:
            List of results (or an awaitable resolving to it)
        """
        # If connection is sync, execute sync logic immediately
        if not self.connection.is_async():
            return self.all_sync(**kwargs)

        return self._all_async(**kwargs)

    async def _all_async(self, **kwargs: Any) -> List[Any]:
        """Internal method to execute the query and return all results asynchronously."""
        raise NotImplementedError("Subclasses must implement _all_async or all")

    def all_sync(self, **kwargs: Any) -> List[Any]:
        """Execute the query and return all results synchronously.

        This method must be implemented by subclasses to execute the query
        and return the results.

        Args:
            **kwargs: Additional arguments (e.g. dereference)

        Returns:
            List of results

        Raises:
            NotImplementedError: If not implemented by a subclass
        """
        raise NotImplementedError("Subclasses must implement all_sync")

    def first(self) -> Union[Optional[Any], Any]:
        """Execute the query and return the first result.

        Polyglot method: executes synchronously if the connection is synchronous,
        otherwise returns an awaitable.

        Returns:
            The first result or None (or an awaitable resolving to it)
        """
        # If connection is sync, execute sync logic immediately
        if not self.connection.is_async():
            return self.first_sync()

        return self._first_async()

    async def _first_async(self) -> Optional[Any]:
        """Internal method to execute the query and return the first result asynchronously."""
        self.limit_value = 1
        results = await self.all()
        return results[0] if results else None

    def first_sync(self) -> Optional[Any]:
        """Execute the query and return the first result synchronously.

        This method limits the query to one result and returns the first item
        or None if no results are found.

        Returns:
            The first result or None if no results
        """
        self.limit_value = 1
        results = self.all_sync()
        return results[0] if results else None

    def get(self, **kwargs) -> Union[Any, Any]:
        """Get a single document matching the query.

        Polyglot method: executes synchronously if the connection is synchronous,
        otherwise returns an awaitable.

        Args:
            **kwargs: Field names and values to filter by

        Returns:
            The matching document (or an awaitable resolving to it)

        Raises:
            DoesNotExist: If no matching document is found
            MultipleObjectsReturned: If multiple matching documents are found
        """
        # Special handling for ID-based lookup
        if len(kwargs) == 1 and "id" in kwargs:
            id_value = kwargs["id"]
            # If it's already a full record ID (table:id format)
            if isinstance(id_value, str) and ":" in id_value:
                query = f"SELECT * FROM {id_value}"
            else:
                # Get table name from document class if available
                table_name = getattr(self, "document_class", None)
                if table_name:
                    table_name = table_name._get_collection_name()
                else:
                    table_name = getattr(self, "table_name", None)

                if table_name:
                    query = f"SELECT * FROM {table_name}:{id_value}"
                else:
                    # Fall back to regular filtering if we can't determine the table
                    if not self.connection.is_async():
                        return self._get_with_filters_sync(**kwargs)
                    return self._get_with_filters(**kwargs)

            # Execution based on connection type
            if not self.connection.is_async():
                result = self.connection.client.query(query)
                if not result or not result[0]:
                    raise DoesNotExist(f"Object with ID '{id_value}' does not exist.")
                return result[0][0]
            else:
                return self._get_id_async(query, id_value)

        # For non-ID lookups, use regular filtering
        if not self.connection.is_async():
            return self._get_with_filters_sync(**kwargs)
        return self._get_with_filters(**kwargs)

    async def _get_id_async(self, query: str, id_value: Any) -> Any:
        """Internal async implementation of ID-based get()."""
        result = await self.connection.client.query(query)
        if not result or not result[0]:
            raise DoesNotExist(f"Object with ID '{id_value}' does not exist.")
        return result[0][0]

    def get_sync(self, **kwargs) -> Any:
        """Get a single document matching the query synchronously.

        This method applies filters and ensures that exactly one document is returned.
        For ID-based lookups, it uses direct record syntax instead of WHERE clause.

        Args:
            **kwargs: Field names and values to filter by

        Returns:
            The matching document

        Raises:
            DoesNotExist: If no matching document is found
            MultipleObjectsReturned: If multiple matching documents are found
        """
        # Special handling for ID-based lookup
        if len(kwargs) == 1 and "id" in kwargs:
            id_value = kwargs["id"]
            # If it's already a full record ID (table:id format)
            if isinstance(id_value, str) and ":" in id_value:
                query = f"SELECT * FROM {id_value}"
            else:
                # Get table name from document class if available
                table_name = getattr(self, "document_class", None)
                if table_name:
                    table_name = table_name._get_collection_name()
                else:
                    table_name = getattr(self, "table_name", None)

                if table_name:
                    query = f"SELECT * FROM {table_name}:{id_value}"
                else:
                    # Fall back to regular filtering if we can't determine the table
                    return self._get_with_filters_sync(**kwargs)

            result = self.connection.client.query(query)
            if not result or not result[0]:
                raise DoesNotExist(f"Object with ID '{id_value}' does not exist.")
            return result[0][0]

        # For non-ID lookups, use regular filtering
        return self._get_with_filters_sync(**kwargs)

    async def _get_with_filters(self, **kwargs) -> Any:
        """Internal method to get a single document using filters asynchronously.

        Args:
            **kwargs: Field names and values to filter by

        Returns:
            The matching document

        Raises:
            DoesNotExist: If no matching document is found
            MultipleObjectsReturned: If multiple matching documents are found
        """
        self.filter(**kwargs)
        self.limit_value = 2  # Get 2 to check for multiple
        results = await self.all()

        if not results:
            raise DoesNotExist("Object matching query does not exist.")
        if len(results) > 1:
            raise MultipleObjectsReturned("Multiple objects returned instead of one")

        return results[0]

    def _get_with_filters_sync(self, **kwargs) -> Any:
        """Internal method to get a single document using filters synchronously.

        Args:
            **kwargs: Field names and values to filter by

        Returns:
            The matching document

        Raises:
            DoesNotExist: If no matching document is found
            MultipleObjectsReturned: If multiple matching documents are found
        """
        self.filter(**kwargs)
        self.limit_value = 2  # Get 2 to check for multiple
        results = self.all_sync()

        if not results:
            raise DoesNotExist("Object matching query does not exist.")
        if len(results) > 1:
            raise MultipleObjectsReturned("Multiple objects returned instead of one")

        return results[0]

    def count(self) -> Union[int, Any]:
        """Count documents matching the query.

        Polyglot method: executes synchronously if the connection is synchronous,
        otherwise returns an awaitable.

        Returns:
            Number of matching documents (or an awaitable resolving to it)
        """
        # If connection is sync, execute sync logic immediately
        if not self.connection.is_async():
            return self.count_sync()

        return self._count_async()

    async def _count_async(self) -> int:
        """Internal method to count documents matching the query asynchronously."""
        raise NotImplementedError("Subclasses must implement _count_async or count")

    def count_sync(self) -> int:
        """Count documents matching the query synchronously.

        This method must be implemented by subclasses to count the number
        of documents matching the query.

        Returns:
            Number of matching documents

        Raises:
            NotImplementedError: If not implemented by a subclass
        """
        raise NotImplementedError("Subclasses must implement count_sync")

    def __await__(self):
        """Make the queryset awaitable.

        This method allows the queryset to be used with the await keyword,
        which will execute the query and return all results.

        Returns:
            Awaitable that resolves to the query results
        """
        return self.all().__await__()

    def page(self, number: int, size: int) -> "BaseQuerySet":
        """Set pagination parameters using page number and size.

        This method calculates the appropriate LIMIT and START values
        based on the page number and size, providing a more convenient
        way to paginate results.

        Args:
            number: Page number (1-based, first page is 1)
            size: Number of items per page

        Returns:
            The query set instance for method chaining
        """
        if number < 1:
            raise ValueError("Page number must be 1 or greater")
        if size < 1:
            raise ValueError("Page size must be 1 or greater")

        self.limit_value = size
        self.start_value = (number - 1) * size
        return self

    def paginate(self, page: int, per_page: int) -> Union[PaginationResult, Any]:
        """Get a page of results with pagination metadata.

        Polyglot method: executes synchronously if the connection is synchronous,
        otherwise returns an awaitable.

        Args:
            page: The page number (1-based)
            per_page: The number of items per page

        Returns:
            A PaginationResult containing the items and pagination metadata
            (or awaitable resolving to it)
        """
        # If connection is sync, execute sync logic immediately
        if not self.connection.is_async():
            return self.paginate_sync(page, per_page)

        return self._paginate_async(page, per_page)

    async def _paginate_async(self, page: int, per_page: int) -> PaginationResult:
        """Internal async implementation of paginate()."""
        # Get the total count
        total = await self.count()

        # Get the items for the current page
        items = await self.page(page, per_page).all()

        # Return a PaginationResult
        return PaginationResult(items, page, per_page, total)

    def paginate_sync(self, page: int, per_page: int) -> PaginationResult:
        """Get a page of results with pagination metadata synchronously.

        This method gets a page of results along with metadata about the
        pagination, such as the total number of items, the number of pages,
        and whether there are next or previous pages.

        Args:
            page: The page number (1-based)
            per_page: The number of items per page

        Returns:
            A PaginationResult containing the items and pagination metadata
        """
        # Get the total count
        total = self.count_sync()

        # Get the items for the current page
        items = self.page(page, per_page).all_sync()

        # Return a PaginationResult
        return PaginationResult(items, page, per_page, total)

    def get_raw_query(self) -> str:
        """Get the raw query string without executing it.

        This method builds and returns the query string without executing it.
        It can be used to get the raw query for manual execution or debugging.

        Returns:
            The raw query string
        """
        return self._build_query()

    def aggregate(self):
        """Create an aggregation pipeline from this query.

        This method returns an AggregationPipeline instance that can be used
        to build and execute complex aggregation queries with multiple stages.

        Returns:
            An AggregationPipeline instance for building and executing
            aggregation queries.
        """
        from .aggregation import AggregationPipeline

        return AggregationPipeline(self)

    def _clone(self: T) -> T:
        """Create a new instance of the queryset with the same parameters.

        This method creates a new instance of the same class as the current
        instance and copies all the relevant attributes.

        Returns:
            A new queryset instance with the same parameters
        """
        # Create a new instance of the same class
        if hasattr(self, "document_class"):
            # For QuerySet subclass
            clone = self.__class__(self.document_class, self.connection)
        elif hasattr(self, "table_name"):
            # For SchemalessQuerySet subclass
            clone = self.__class__(self.table_name, self.connection)
        else:
            # For BaseQuerySet or other subclasses
            clone = self.__class__(self.connection)

        # Copy all the query parameters
        clone.query_parts = self.query_parts.copy()
        clone.limit_value = self.limit_value
        clone.start_value = self.start_value
        clone.order_by_value = self.order_by_value
        clone.group_by_fields = self.group_by_fields.copy()
        clone.split_fields = self.split_fields.copy()
        clone.fetch_fields = self.fetch_fields.copy()
        clone.with_index = self.with_index
        clone.select_fields = self.select_fields
        # Copy performance optimization attributes
        clone._bulk_id_selection = self._bulk_id_selection
        clone._id_range_selection = self._id_range_selection
        clone._prefer_direct_access = self._prefer_direct_access
        # Copy traversal state
        clone._traversal_path = self._traversal_path
        clone._traversal_unique = self._traversal_unique
        clone._traversal_max_depth = self._traversal_max_depth

        return clone  # type: ignore
