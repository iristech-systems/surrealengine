from typing import Any, Dict, List, Optional

from .base import Field
from ..exceptions import ValidationError

class GeometryField(Field):
    """Field for handling geometric data in SurrealDB.

    This field validates and processes geometric data according to SurrealDB's
    geometry specification. It supports various geometry types including Point,
    LineString, Polygon, MultiPoint, MultiLineString, and MultiPolygon.

    Attributes:
        required (bool): Whether the field is required. Defaults to False.

    Example:
        ```python
        class Location(Document):
            point = GeometryField()

        # Using GeometryPoint for precise coordinate handling
        from surrealengine.geometry import GeometryPoint
        loc = Location(point=GeometryPoint([-122.4194, 37.7749]))
        ```
    """

    def __init__(self, required: bool = False, **kwargs):
        """Initialize a GeometryField.

        Args:
            required (bool, optional): Whether this field is required. Defaults to False.
            **kwargs: Additional field options to be passed to the parent Field class.
        """
        super().__init__(required=required, **kwargs)
        self.py_type = dict

    def validate(self, value):
        """Validate geometry data.

        Ensures the geometry data follows SurrealDB's expected format with proper structure
        and coordinates. Does not modify the numeric values to preserve SurrealDB's
        native geometry handling.

        Args:
            value: The geometry value to validate. Can be a GeometryPoint object or
                  a dict with 'type' and 'coordinates' fields.

        Returns:
            dict: The validated geometry data.

        Raises:
            ValidationError: If the geometry data is invalid or improperly formatted.
        """
        if value is None:
            if self.required:
                raise ValidationError("This field is required")
            return None

        # Handle GeometryPoint and other Geometry objects
        if hasattr(value, 'to_json'):
            return value.to_json()
        
        # Handle GeometryPoint from surrealdb.data
        if hasattr(value, 'get_coordinates') and hasattr(value, 'longitude') and hasattr(value, 'latitude'):
            coords = value.get_coordinates()
            # Use simple tuple format as preferred by SurrealDB
            return list(coords)  # Convert tuple to list for JSON serialization

        # Handle simple coordinate arrays for Point geometry (longitude, latitude)
        if isinstance(value, (list, tuple)) and len(value) == 2:
            try:
                # Validate that coordinates are numeric
                float(value[0])  # longitude
                float(value[1])  # latitude
                return list(value)  # Convert to list for consistency
            except (TypeError, ValueError):
                pass  # Fall through to other validation

        if not isinstance(value, dict):
            raise ValidationError("Geometry value must be a dictionary or coordinate array")

        if "type" not in value or "coordinates" not in value:
            raise ValidationError("Geometry must have 'type' and 'coordinates' fields")

        if not isinstance(value["coordinates"], list):
            raise ValidationError("Coordinates must be a list")

        # Validate structure based on geometry type without modifying values
        if value["type"] == "Point":
            if len(value["coordinates"]) != 2:
                raise ValidationError("Point coordinates must be a list of two numbers")
        elif value["type"] in ("LineString", "MultiPoint"):
            if not all(isinstance(point, list) and len(point) == 2 for point in value["coordinates"]):
                raise ValidationError("LineString/MultiPoint coordinates must be a list of [x,y] points")
        elif value["type"] in ("Polygon", "MultiLineString"):
            if not all(isinstance(line, list) and
                       all(isinstance(point, list) and len(point) == 2 for point in line)
                       for line in value["coordinates"]):
                raise ValidationError("Polygon/MultiLineString must be a list of coordinate arrays")
        elif value["type"] == "MultiPolygon":
            if not all(isinstance(polygon, list) and
                       all(isinstance(line, list) and
                           all(isinstance(point, list) and len(point) == 2 for point in line)
                           for line in polygon)
                       for polygon in value["coordinates"]):
                raise ValidationError("MultiPolygon must be a list of polygon arrays")

        return value