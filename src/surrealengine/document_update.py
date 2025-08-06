"""
Extension module for Document update functionality.

This module provides update methods for Document instances
that allow updating specific fields without deleting existing data.
"""

import json
from typing import Any, Optional, Dict, Type

from .document import Document
from .connection import ConnectionRegistry


async def update_document(doc: Document, 
                         connection: Optional[Any] = None, 
                         **attrs: Any) -> Document:
    """Update the document without deleting existing data.
    
    This method updates only the specified attributes of the document
    without affecting other attributes, unlike the save() method which uses upsert.
    
    Args:
        doc: The Document instance to update
        connection: The database connection to use (optional)
        **attrs: Attributes to update on the document
        
    Returns:
        The updated document
        
    Raises:
        ValueError: If the document is not saved
    """
    if not doc.id:
        raise ValueError("Cannot update unsaved document")
        
    if connection is None:
        connection = ConnectionRegistry.get_default_connection(async_mode=True)
        
    # Update only the specified attributes
    update_query = f"UPDATE {doc.id} SET"
    
    # Add attributes
    updates = []
    for key, value in attrs.items():
        # Update the instance
        setattr(doc, key, value)
        updates.append(f" {key} = {json.dumps(value)}")
        
    if not updates:
        return doc
        
    update_query += ",".join(updates)
    
    result = await connection.client.query(update_query)
    
    if result and result[0]:
        # Mark the updated fields as clean
        for key in attrs:
            if key in doc._changed_fields:
                doc._changed_fields.remove(key)
                
        # Update the original values
        for key, value in attrs.items():
            if hasattr(doc, '_original_data'):
                doc._original_data[key] = value
            
    return doc
    
def update_document_sync(doc: Document, 
                        connection: Optional[Any] = None, 
                        **attrs: Any) -> Document:
    """Update the document without deleting existing data synchronously.
    
    This method updates only the specified attributes of the document
    without affecting other attributes, unlike the save() method which uses upsert.
    
    Args:
        doc: The Document instance to update
        connection: The database connection to use (optional)
        **attrs: Attributes to update on the document
        
    Returns:
        The updated document
        
    Raises:
        ValueError: If the document is not saved
    """
    if not doc.id:
        raise ValueError("Cannot update unsaved document")
        
    if connection is None:
        connection = ConnectionRegistry.get_default_connection(async_mode=False)
        
    # Update only the specified attributes
    update_query = f"UPDATE {doc.id} SET"
    
    # Add attributes
    updates = []
    for key, value in attrs.items():
        # Update the instance
        setattr(doc, key, value)
        updates.append(f" {key} = {json.dumps(value)}")
        
    if not updates:
        return doc
        
    update_query += ",".join(updates)
    
    result = connection.client.query(update_query)
    
    if result and result[0]:
        # Mark the updated fields as clean
        for key in attrs:
            if key in doc._changed_fields:
                doc._changed_fields.remove(key)
                
        # Update the original values
        for key, value in attrs.items():
            if hasattr(doc, '_original_data'):
                doc._original_data[key] = value
            
    return doc

# Monkey patch the Document class to add the update methods
def patch_document():
    """Add update methods to Document class and modify save methods.
    
    This function:
    1. Adds update() and update_sync() methods to Document
    2. Modifies the original save() and save_sync() methods to use update() for existing documents
    """
    # Store original save methods
    original_save = Document.save
    original_save_sync = Document.save_sync
    
    # Add update methods
    Document.update = update_document
    Document.update_sync = update_document_sync
    
    # Define new save methods that use update for existing documents
    async def new_save(self, connection=None):
        """Enhanced save method that uses update for existing documents."""
        # If document exists and has changes, use update instead of upsert
        if self.id and self._changed_fields and not isinstance(self, Document.__subclasses__()):
            # Get only the changed data
            data = self.get_changed_data_for_update()
            if data:
                return await self.update(**data)
        
        # Otherwise use the original save method
        return await original_save(self, connection)
    
    def new_save_sync(self, connection=None):
        """Enhanced sync save method that uses update for existing documents."""
        # If document exists and has changes, use update instead of upsert
        if self.id and self._changed_fields and not isinstance(self, Document.__subclasses__()):
            # Get only the changed data
            data = self.get_changed_data_for_update()
            if data:
                return self.update_sync(**data)
        
        # Otherwise use the original save method
        return original_save_sync(self, connection)
    
    # Replace save methods
    Document.save = new_save
    Document.save_sync = new_save_sync