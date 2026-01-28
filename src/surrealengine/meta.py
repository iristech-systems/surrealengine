from typing import List, Dict, Any, Optional


class DocumentMetaOptions:
    """
    Options for configuring a Document model.

    To use, create an inner class `Meta` in your `Document` subclass
    that inherits from `DocumentMetaOptions`.
    """
    collection: Optional[str] = None
    """Name of the database collection/table. Defaults to lowercase class name."""

    indexes: Optional[List[Dict[str, Any]]] = None
    """
    List of index definitions. Each index dict can contain:
    - name (str): Custom name for the index
    - fields (List[str]): Field names to include in the index
    - unique (bool): Whether the index enforces uniqueness
    - search (bool): Whether the index is a search index (simple)
    - analyzer (str): Analyzer to use for search indexes
    # Vector Search specific
    - dimension (int): Dimension of the vector (implies HNSW)
    - dist (str): Distance function ('COSINE', 'EUCLIDEAN', 'MANHATTAN', 'HAMMING')
    - m (int): HNSW M parameter
    - efc (int): HNSW EFC parameter
    - m0 (int): HNSW M0 parameter
    # Full Text Search specific
    - highlights (bool): Enable highlighting for FTS
    - bm25 (bool): Enable BM25 scoring for FTS
    - comment (str): Optional comment for the index
    """

    events: Optional[List[Any]] = None
    """
    List of Event objects defining triggers for this table.
    """

    id_field: Optional[str] = None
    """Name of the ID field. Defaults to "id"."""

    strict: Optional[bool] = None
    """
    Whether to enforce strict field validation. Defaults to True.
    When False, allows dynamic fields not defined in the schema.
    """

    time_series: Optional[bool] = None
    """Whether this is a time series table. Defaults to False."""

    time_field: Optional[str] = None
    """Field to use for time series timestamp. Required when time_series is True."""

    abstract: Optional[bool] = None
    """
    Whether this document is abstract. Abstract documents are not registered
    with the database and are meant to be inherited.
    """