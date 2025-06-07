from typing import Any, List, TypeVar, Generic, Iterator, Sequence

T = TypeVar('T')

class PaginationResult(Generic[T]):
    """Container for paginated query results with metadata.
    
    This class provides a container for paginated query results along with
    metadata about the pagination, such as the total number of items,
    the number of pages, and whether there are next or previous pages.
    
    Attributes:
        items: The items in the current page
        page: The current page number
        per_page: The number of items per page
        total: The total number of items across all pages
        pages: The total number of pages
        has_next: Whether there is a next page
        has_prev: Whether there is a previous page
    """
    
    def __init__(self, items: List[T], page: int, per_page: int, total: int):
        """Initialize a PaginationResult.
        
        Args:
            items: The items in the current page
            page: The current page number
            per_page: The number of items per page
            total: The total number of items across all pages
        """
        self.items = items
        self.page = page
        self.per_page = per_page
        self.total = total
        self.pages = (total + per_page - 1) // per_page if per_page > 0 else 0  # Ceiling division
        self.has_next = page < self.pages
        self.has_prev = page > 1
        
    def __iter__(self) -> Iterator[T]:
        """Iterate over the items in the current page."""
        return iter(self.items)
        
    def __len__(self) -> int:
        """Get the number of items in the current page."""
        return len(self.items)
        
    def __getitem__(self, index: int) -> T:
        """Get an item from the current page by index."""
        return self.items[index]
    
    def __repr__(self) -> str:
        """Get a string representation of the pagination result."""
        return f"<PaginationResult page={self.page} per_page={self.per_page} total={self.total} pages={self.pages}>"