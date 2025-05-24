# Re-export classes for backward compatibility
from .base import QuerySet
from .descriptor import QuerySetDescriptor
from .relation import RelationQuerySet

# Export all classes at the top level to maintain the same import interface
__all__ = ['QuerySet', 'QuerySetDescriptor', 'RelationQuerySet']
