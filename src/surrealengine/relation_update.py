"""
Extension module for RelationDocument update functionality.

This module provides update methods for RelationDocument instances
that allow updating specific fields without deleting existing data.
"""

import json
from typing import Any, Optional, Dict, Type

from .document import RelationDocument
from .connection import ConnectionRegistry


async def update_relation_document(relation_doc: RelationDocument, 
                                  connection: Optional[Any] = None, 
                                  **attrs: Any) -> RelationDocument:
    """Update the relation document without deleting existing data.
    
    This method updates only the specified attributes of the relation document
    without affecting other attributes, unlike the save() method which uses upsert.
    
    Args:
        relation_doc: The RelationDocument instance to update
        connection: The database connection to use (optional)
        **attrs: Attributes to update on the relation
        
    Returns:
        The updated relation document
        
    Raises:
        ValueError: If the document is not saved
    """
    if not relation_doc.id:
        raise ValueError("Cannot update unsaved relation document")
        
    if connection is None:
        connection = ConnectionRegistry.get_default_connection(async_mode=True)
        
    # Update only the specified attributes
    update_query = f"UPDATE {relation_doc.id} SET"
    
    # Add attributes
    updates = []
    from .document import _serialize_for_surreal as _ser
    for key, value in attrs.items():
        # Update the instance
        setattr(relation_doc, key, value)
        updates.append(f" {key} = {_ser(value)}")
        
    if not updates:
        return relation_doc
        
    update_query += ",".join(updates)
    
    result = await connection.client.query(update_query)
    
    if result and result[0]:
        # Mark the updated fields as clean
        for key in attrs:
            if key in relation_doc._changed_fields:
                relation_doc._changed_fields.remove(key)
                
        # Update the original values
        for key, value in attrs.items():
            if hasattr(relation_doc, '_original_data'):
                relation_doc._original_data[key] = value
            
    return relation_doc
    
def update_relation_document_sync(relation_doc: RelationDocument, 
                                 connection: Optional[Any] = None, 
                                 **attrs: Any) -> RelationDocument:
    """Update the relation document without deleting existing data synchronously.
    
    This method updates only the specified attributes of the relation document
    without affecting other attributes, unlike the save() method which uses upsert.
    
    Args:
        relation_doc: The RelationDocument instance to update
        connection: The database connection to use (optional)
        **attrs: Attributes to update on the relation
        
    Returns:
        The updated relation document
        
    Raises:
        ValueError: If the document is not saved
    """
    if not relation_doc.id:
        raise ValueError("Cannot update unsaved relation document")
        
    if connection is None:
        connection = ConnectionRegistry.get_default_connection(async_mode=False)
        
    # Update only the specified attributes
    update_query = f"UPDATE {relation_doc.id} SET"
    
    # Add attributes
    updates = []
    from .document import _serialize_for_surreal as _ser
    for key, value in attrs.items():
        # Update the instance
        setattr(relation_doc, key, value)
        updates.append(f" {key} = {_ser(value)}")
        
    if not updates:
        return relation_doc
        
    update_query += ",".join(updates)
    
    result = connection.client.query(update_query)
    
    if result and result[0]:
        # Mark the updated fields as clean
        for key in attrs:
            if key in relation_doc._changed_fields:
                relation_doc._changed_fields.remove(key)
                
        # Update the original values
        for key, value in attrs.items():
            if hasattr(relation_doc, '_original_data'):
                relation_doc._original_data[key] = value
            
    return relation_doc

# Monkey patch the RelationDocument class to add the update methods
def patch_relation_document():
    """Add update methods to RelationDocument class."""
    RelationDocument.update = update_relation_document
    RelationDocument.update_sync = update_relation_document_sync