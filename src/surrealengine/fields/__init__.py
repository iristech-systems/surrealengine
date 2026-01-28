# Re-export all field classes for backward compatibility
from .base import Field
from .scalar import (
    StringField, NumberField, IntField, FloatField, BooleanField
)
from .datetime import (
    DateTimeField, TimeSeriesField, DurationField
)
from .collection import (
    ListField, DictField, SetField
)
from .reference import (
    ReferenceField, RelationField
)
from .geometry import GeometryField
from .id import RecordIDField
from .specialized import (
    BytesField, RegexField, DecimalField, UUIDField, LiteralField,
    EmailField, URLField, IPAddressField, SlugField, ChoiceField, VectorField
)
from .additional import (
    OptionField, FutureField, TableField, RangeField
)
from .embedded import EmbeddedField

# Export all classes at the top level to maintain the same import interface
__all__ = [
    'Field',
    'StringField', 'NumberField', 'IntField', 'FloatField', 'BooleanField',
    'DateTimeField', 'TimeSeriesField', 'DurationField',
    'ListField', 'DictField', 'SetField',
    'ReferenceField', 'RelationField',
    'GeometryField',
    'RecordIDField',
    'BytesField', 'RegexField', 'DecimalField', 'UUIDField', 'LiteralField',
    'EmailField', 'URLField', 'IPAddressField', 'SlugField', 'ChoiceField', 'VectorField',
    'OptionField', 'FutureField', 'TableField', 'RangeField', 'EmbeddedField',
]
