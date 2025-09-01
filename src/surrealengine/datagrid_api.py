"""
DataGrid Query Helpers for SurrealEngine - Efficient database querying for grid data
"""

from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from decimal import Decimal


class DataGridQueryBuilder:
    """Build efficient SurrealDB queries for DataGrid endpoints"""
    
    def __init__(self, document_class):
        self.document_class = document_class
        self.queryset = document_class.objects
    
    def apply_filters(self, filters: Dict[str, Any]):
        """Apply field filters to the queryset
        
        Args:
            filters: Dictionary of field->value filters
        """
        for field, value in filters.items():
            if value:  # Only apply non-empty filters
                self.queryset = self.queryset.filter(**{field: value})
        return self
    
    def apply_search(self, search: str, search_fields: List[str]):
        """Apply text search across multiple fields using contains operator
        
        Args:
            search: Search term
            search_fields: List of fields to search in
        """
        if search and search_fields:
            # Use the first search field with contains for now
            # This is a simplified implementation - full text search across multiple fields
            # would require raw SurrealQL which might need to be added to SurrealEngine
            if search_fields:
                first_field = search_fields[0]
                self.queryset = self.queryset.filter(**{f"{first_field}__contains": search})
        
        return self
    
    def apply_sorting(self, sort_field: Optional[str] = None, sort_order: str = 'asc'):
        """Apply sorting to the queryset
        
        Args:
            sort_field: Field to sort by
            sort_order: 'asc' or 'desc'
        """
        if sort_field:
            order_by = sort_field if sort_order == 'asc' else f'-{sort_field}'
            self.queryset = self.queryset.order_by(order_by)
        
        return self
    
    async def get_paginated_data(self, offset: int, limit: int):
        """Get paginated data with total count
        
        Args:
            offset: Number of records to skip
            limit: Number of records to return
            
        Returns:
            Tuple of (total_count, paginated_results)
        """
        # Get total count before pagination
        total = await self.queryset.count()
        
        # Get paginated results using SurrealEngine's pagination methods
        results = await self.queryset.start(offset).limit(limit).all()
        
        return total, results
    
    def get_paginated_data_sync(self, offset: int, limit: int):
        """Synchronous version of get_paginated_data"""
        total = self.queryset.count_sync()
        results = self.queryset.start(offset).limit(limit).all_sync()
        return total, results


async def get_grid_data(document_class, request_args: Dict[str, Any], 
                       search_fields: List[str], 
                       custom_filters: Optional[Dict[str, str]] = None,
                       default_sort: Optional[str] = None) -> Dict[str, Any]:
    """Get paginated grid data using efficient SurrealDB queries
    
    Args:
        document_class: SurrealEngine document class
        request_args: Request parameters (limit, offset, search, etc.)
        search_fields: List of fields to search in
        custom_filters: Custom field filters from request
        default_sort: Default sorting field
    
    Returns:
        {"total": total, "rows": rows} for BootstrapTable format
    """
    # Parse request parameters
    limit = int(request_args.get('limit', 25))
    offset = int(request_args.get('offset', 0))
    search = request_args.get('search', '')
    sort_field = request_args.get('sort', default_sort)
    sort_order = request_args.get('order', 'asc')
    
    # Build query
    builder = DataGridQueryBuilder(document_class)
    
    # Apply custom filters
    if custom_filters:
        filters = {}
        for param_name, field_name in custom_filters.items():
            value = request_args.get(param_name)
            if value:
                filters[field_name] = value
        builder.apply_filters(filters)
    
    # Apply search
    builder.apply_search(search, search_fields)
    
    # Apply sorting
    builder.apply_sorting(sort_field, sort_order)
    
    # Get paginated data
    total, results = await builder.get_paginated_data(offset, limit)
    
    # Convert to dictionaries
    rows = []
    for obj in results:
        if hasattr(obj, 'to_dict'):
            row_data = obj.to_dict()
        else:
            row_data = {field: getattr(obj, field, None) for field in obj._fields.keys()}
        
        # Serialize complex types
        serialized_row = {}
        for key, value in row_data.items():
            if isinstance(value, datetime):
                serialized_row[key] = value.strftime('%Y-%m-%d') if value else None
            elif isinstance(value, Decimal):
                serialized_row[key] = float(value) if value is not None else None
            elif hasattr(value, 'id'):  # Handle record references
                serialized_row[key] = str(value.id) if value else None
            else:
                serialized_row[key] = value
        
        rows.append(serialized_row)
    
    return {"total": total, "rows": rows}


def get_grid_data_sync(document_class, request_args: Dict[str, Any], 
                      search_fields: List[str], 
                      custom_filters: Optional[Dict[str, str]] = None,
                      default_sort: Optional[str] = None) -> Dict[str, Any]:
    """Synchronous version of get_grid_data"""
    # Parse request parameters
    limit = int(request_args.get('limit', 25))
    offset = int(request_args.get('offset', 0))
    search = request_args.get('search', '')
    sort_field = request_args.get('sort', default_sort)
    sort_order = request_args.get('order', 'asc')
    
    # Build query
    builder = DataGridQueryBuilder(document_class)
    
    # Apply custom filters
    if custom_filters:
        filters = {}
        for param_name, field_name in custom_filters.items():
            value = request_args.get(param_name)
            if value:
                filters[field_name] = value
        builder.apply_filters(filters)
    
    # Apply search
    builder.apply_search(search, search_fields)
    
    # Apply sorting
    builder.apply_sorting(sort_field, sort_order)
    
    # Get paginated data
    total, results = builder.get_paginated_data_sync(offset, limit)
    
    # Convert to dictionaries
    rows = []
    for obj in results:
        if hasattr(obj, 'to_dict'):
            row_data = obj.to_dict()
        else:
            row_data = {field: getattr(obj, field, None) for field in obj._fields.keys()}
        
        # Serialize complex types
        serialized_row = {}
        for key, value in row_data.items():
            if isinstance(value, datetime):
                serialized_row[key] = value.strftime('%Y-%m-%d') if value else None
            elif isinstance(value, Decimal):
                serialized_row[key] = float(value) if value is not None else None
            elif hasattr(value, 'id'):  # Handle record references
                serialized_row[key] = str(value.id) if value else None
            else:
                serialized_row[key] = value
        
        rows.append(serialized_row)
    
    return {"total": total, "rows": rows}


# For DataTables support
def parse_datatables_params(request_args: Dict[str, Any]) -> Dict[str, Any]:
    """Convert DataTables parameters to standard offset/limit format"""
    start = int(request_args.get('start', 0))
    length = int(request_args.get('length', 10))
    draw = int(request_args.get('draw', 1))
    search = request_args.get('search[value]', '')
    
    return {
        'offset': start,
        'limit': length,
        'search': search,
        'draw': draw
    }


def format_datatables_response(total: int, rows: List[Dict[str, Any]], draw: int) -> Dict[str, Any]:
    """Format response for DataTables"""
    return {
        "draw": draw,
        "recordsTotal": total,
        "recordsFiltered": total,
        "data": rows
    }

