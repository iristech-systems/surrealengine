from datetime import datetime
from typing import Any, Optional, Union
from .document import Document
from .fields import DateTimeField


class TimestampMixin(Document):
    """
    Automatically tracks document creation and update times.

    Adds `created_at` and `updated_at` fields to any inheriting Document class.
    Stamping is handled by DateTimeField's auto_now_add / auto_now support,
    which fires inside save() before validation.

    Note: unlike earlier versions of this mixin, ``updated_at`` now bumps on
    every successful save (not only when other fields changed), and values
    are timezone-aware UTC datetimes.
    """

    class Meta:
        abstract = True

    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)

    def clean(self) -> None:
        """No-op kept for MRO compatibility.

        Subclasses commonly call ``super().clean()``; before auto-datetime
        support existed this method did the timestamping. That work now
        happens in ``Document.save()`` via DateTimeField's auto flags, so
        this hook intentionally does nothing.
        """
        pass


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
