from datetime import datetime
from typing import Any, Optional, Union
from .document import Document
from .fields import DateTimeField


class TimestampMixin(Document):
    """
    Automatically tracks document creation and update times.
    
    Adds `created_at` and `updated_at` fields to any inheriting Document class.
    Automatically manages these timestamps on `.save()`.
    """
    class Meta:
        abstract = True
    
    created_at = DateTimeField(required=False)
    updated_at = DateTimeField(required=False)

    def clean(self) -> None:
        """Update the updated_at timestamp right before saving."""
        super().clean() if hasattr(super(), 'clean') else None
        
        now = datetime.utcnow()
        if not self.created_at:
            self.created_at = now
            
        # We only update updated_at if the document is not completely new
        # and has actual changes.
        if getattr(self, "id", None) is not None and self.has_changed():
            self.updated_at = now
        elif not getattr(self, "id", None):
            # Also set updated_at on first creation to match created_at
            self.updated_at = now


class SoftDeleteMixin(Document):
    """
    Enables soft-delete functionality for documents.
    
    Instead of permanently removing records from the database via `DELETE`,
    records are marked with a `deleted_at` timestamp.
    """
    class Meta:
        abstract = True
    
    deleted_at = DateTimeField(required=False)

    async def delete(self) -> None:
        """Override the default async delete to perform a soft delete."""
        self.deleted_at = datetime.utcnow()
        await self.save()

    def delete_sync(self) -> None:
        """Override the default sync delete to perform a soft delete."""
        self.deleted_at = datetime.utcnow()
        self.save_sync()

    async def hard_delete(self) -> None:
        """Permanently remove the document from the database asynchronously."""
        if hasattr(super(), 'delete'):
            await super().delete()

    def hard_delete_sync(self) -> None:
        """Permanently remove the document from the database synchronously."""
        if hasattr(super(), 'delete_sync'):
            super().delete_sync()
