import datetime
from typing import Any, Optional

# Robust import for SDK wrapper across versions
try:
    from surrealdb.data.types.datetime import IsoDateTimeWrapper  # new path
except Exception:  # pragma: no cover
    try:
        from surrealdb.types import IsoDateTimeWrapper  # possible older path
    except Exception:
        IsoDateTimeWrapper = None  # Fallback handled at runtime

from .base import Field

class DateTimeField(Field):
    """DateTime field type.

    This field type stores datetime values and provides validation and
    conversion between Python datetime objects and SurrealDB datetime format.

    SurrealDB v2.0.0+ requires datetime values to have a `d` prefix or be cast
    as <datetime>. This field handles the conversion automatically, so you can
    use standard Python datetime objects in your code.

    Example:
        ```python
        class Event(Document):
            created_at = DateTimeField(default=datetime.datetime.now)
            scheduled_for = DateTimeField()

        # Python datetime objects are automatically converted to SurrealDB format
        event = Event(scheduled_for=datetime.datetime.now() + datetime.timedelta(days=7))
        await event.save()
        ```
    """

    def __init__(self, **kwargs: Any) -> None:
        """Initialize a new DateTimeField.

        Args:
            **kwargs: Additional arguments to pass to the parent class
        """
        super().__init__(**kwargs)
        self.py_type = datetime.datetime

    def validate(self, value: Any) -> Optional[datetime.datetime]:
        """Validate the datetime value.

        Accepts datetime, IsoDateTimeWrapper, ISO strings (with optional Z or space separator),
        Surreal d'...' literals, and epoch seconds/milliseconds (int/float).
        """
        value = super().validate(value)
        if value is None:
            return None

        # Already a datetime
        if isinstance(value, datetime.datetime):
            return value

        # SDK wrapper instance provided directly
        if IsoDateTimeWrapper is not None and isinstance(value, IsoDateTimeWrapper):
            inner = getattr(value, 'dt', None)
            if isinstance(inner, datetime.datetime):
                return inner
            if isinstance(inner, str):
                try:
                    return datetime.datetime.fromisoformat(inner.replace('Z', '+00:00'))
                except ValueError:
                    pass
            inner_iso = getattr(value, 'iso', None)
            if isinstance(inner_iso, str):
                try:
                    return datetime.datetime.fromisoformat(inner_iso.replace('Z', '+00:00'))
                except ValueError:
                    pass
            # If wrapper can't be unpacked, treat as invalid
            raise TypeError(f"Expected datetime-compatible value for field '{self.name}', got IsoDateTimeWrapper with unknown payload")

        # Epoch seconds or milliseconds
        if isinstance(value, (int, float)):
            seconds = value / 1000.0 if value >= 1_000_000_000_000 else float(value)
            try:
                return datetime.datetime.fromtimestamp(seconds, tz=datetime.timezone.utc)
            except (OverflowError, OSError, ValueError):
                raise TypeError(f"Numeric value for '{self.name}' is not a valid epoch timestamp")

        # Strings (ISO, Surreal literal, with spaces, with Z)
        if isinstance(value, str):
            s = value.strip()
            if s.startswith("d'") and s.endswith("'"):
                s = s[2:-1]
            s_norm = s.replace('Z', '+00:00')
            try:
                return datetime.datetime.fromisoformat(s_norm)
            except ValueError:
                pass
            if ' ' in s_norm and 'T' not in s_norm:
                try:
                    return datetime.datetime.fromisoformat(s_norm.replace(' ', 'T', 1))
                except ValueError:
                    pass
            raise TypeError(f"String value for '{self.name}' is not a valid datetime: {value!r}")

        # Unknown type
        raise TypeError(f"Expected datetime for field '{self.name}', got {type(value)}")

    def to_db(self, value: Any) -> Optional[Any]:
        """Convert Python datetime to database representation.

        This method converts a Python datetime object (or ISO-like string) to a SurrealDB datetime
        type using the SDK's IsoDateTimeWrapper so that schemafull TYPE datetime is satisfied.
        If a naive datetime is provided, assume UTC to avoid ambiguity.
        """
        if value is None:
            return None
        # Coerce from string when possible
        if isinstance(value, str):
            try:
                # Normalize trailing Z to +00:00 for fromisoformat
                value = datetime.datetime.fromisoformat(value.replace('Z', '+00:00'))
            except ValueError:
                # Let SDK try to handle unknown string as-is (unlikely)
                return value
        # Direct wrapper passthrough
        if IsoDateTimeWrapper is not None and isinstance(value, IsoDateTimeWrapper):
            return value
        if isinstance(value, (int, float)):
            # treat as epoch seconds or milliseconds
            seconds = value / 1000.0 if value >= 1_000_000_000_000 else float(value)
            try:
                value = datetime.datetime.fromtimestamp(seconds, tz=datetime.timezone.utc)
            except Exception:
                return value
        if isinstance(value, datetime.datetime):
            # Ensure timezone-aware; default to UTC if naive
            if value.tzinfo is None:
                value = value.replace(tzinfo=datetime.timezone.utc)
            # Prefer SDK wrapper when available
            if IsoDateTimeWrapper is not None:
                try:
                    return IsoDateTimeWrapper(value)  # some SDKs accept dt directly
                except Exception:
                    try:
                        return IsoDateTimeWrapper(value.isoformat())
                    except Exception:
                        pass
            # Fallback to Surreal literal
            return f"d'{value.isoformat().replace('+00:00','Z')}'"
        return value

    def from_db(self, value: Any) -> Optional[datetime.datetime]:
        """Convert database value to Python datetime.

        Accepts IsoDateTimeWrapper, Surreal d'...' literal strings, ISO strings (with optional Z),
        or datetime instances. Returns a Python datetime (timezone-aware if source has offset).
        """
        if value is None:
            return None
        # SDK wrapper: value.dt may be an ISO string
        if IsoDateTimeWrapper is not None and isinstance(value, IsoDateTimeWrapper):
            s = getattr(value, 'dt', None)
            if isinstance(s, str):
                try:
                    return datetime.datetime.fromisoformat(s.replace('Z', '+00:00'))
                except ValueError:
                    return None
            if isinstance(s, datetime.datetime):
                return s
            # Some SDKs may use 'iso'
            s2 = getattr(value, 'iso', None)
            if isinstance(s2, str):
                try:
                    return datetime.datetime.fromisoformat(s2.replace('Z', '+00:00'))
                except ValueError:
                    return None
            return None
        # Surreal datetime literal like d'2025-08-31T12:34:56Z'
        if isinstance(value, str):
            s = value
            if s.startswith("d'") and s.endswith("'"):
                s = s[2:-1]
            try:
                return datetime.datetime.fromisoformat(s.replace('Z', '+00:00'))
            except ValueError:
                return None
        if isinstance(value, datetime.datetime):
            return value
        return None


class TimeSeriesField(DateTimeField):
    """Field for time series data.

    This field type extends DateTimeField and adds support for time series data.
    It can be used to store timestamps for time series data and supports
    additional metadata for time series operations.

    Example:
        class SensorReading(Document):
            timestamp = TimeSeriesField(index=True)
            value = FloatField()

            class Meta:
                time_series = True
                time_field = "timestamp"
    """

    def __init__(self, **kwargs: Any) -> None:
        """Initialize a new TimeSeriesField.

        Args:
            **kwargs: Additional arguments to pass to the parent class
        """
        super().__init__(**kwargs)

    def validate(self, value: Any) -> Optional[datetime.datetime]:
        """Validate the timestamp value.

        This method checks if the value is a valid timestamp for time series data.

        Args:
            value: The value to validate

        Returns:
            The validated timestamp value
        """
        return super().validate(value)


class DurationField(Field):
    """Duration field type.

    This field type stores durations of time and provides validation and
    conversion between Python timedelta objects and SurrealDB duration strings.
    """

    def __init__(self, **kwargs: Any) -> None:
        """Initialize a new DurationField.

        Args:
            **kwargs: Additional arguments to pass to the parent class
        """
        super().__init__(**kwargs)
        self.py_type = datetime.timedelta

    def validate(self, value: Any) -> Optional[datetime.timedelta]:
        """Validate the duration value.

        This method checks if the value is a valid timedelta or can be
        converted to a timedelta from a string.

        Args:
            value: The value to validate

        Returns:
            The validated timedelta value

        Raises:
            TypeError: If the value cannot be converted to a timedelta
        """
        value = super().validate(value)
        if value is not None:
            if isinstance(value, datetime.timedelta):
                return value
            if isinstance(value, str):
                try:
                    # Parse SurrealDB duration format (e.g., "1y2m3d4h5m6s")
                    # This is a simplified implementation and may need to be expanded
                    total_seconds = 0
                    num_buffer = ""
                    for char in value:
                        if char.isdigit():
                            num_buffer += char
                        elif char == 'y' and num_buffer:
                            total_seconds += int(num_buffer) * 365 * 24 * 60 * 60
                            num_buffer = ""
                        elif char == 'm' and num_buffer:
                            # Ambiguous: could be month or minute
                            # Assume month if previous char was 'y', otherwise minute
                            if 'y' in value[:value.index(char)]:
                                total_seconds += int(num_buffer) * 30 * 24 * 60 * 60
                            else:
                                total_seconds += int(num_buffer) * 60
                            num_buffer = ""
                        elif char == 'd' and num_buffer:
                            total_seconds += int(num_buffer) * 24 * 60 * 60
                            num_buffer = ""
                        elif char == 'h' and num_buffer:
                            total_seconds += int(num_buffer) * 60 * 60
                            num_buffer = ""
                        elif char == 's' and num_buffer:
                            total_seconds += int(num_buffer)
                            num_buffer = ""
                    return datetime.timedelta(seconds=total_seconds)
                except (ValueError, TypeError):
                    pass
            raise TypeError(f"Expected duration for field '{self.name}', got {type(value)}")
        return value

    def to_db(self, value: Any) -> Optional[Any]:
        """Convert Python timedelta to database representation.

        This method converts a Python timedelta object to a SurrealDB Duration object
        for storage in the database.

        Args:
            value: The Python timedelta to convert

        Returns:
            The SurrealDB Duration object for the database
        """
        if value is None:
            return None

        # Import SurrealDB Duration class
        from surrealdb import Duration

        if isinstance(value, str):
            # If it's already a string, convert to a supported format
            self.validate(value)  # Validate first
            # Convert years to days (approximate: 1 year = 365 days)
            if 'y' in value:
                # Simple conversion for basic year formats like "2y"
                import re
                year_match = re.search(r'(\d+)y', value)
                if year_match:
                    years = int(year_match.group(1))
                    days = years * 365
                    # Replace the year part with days
                    converted = re.sub(r'\d+y', f'{days}d', value)
                    return Duration.parse(converted)
            return Duration.parse(value)

        if isinstance(value, datetime.timedelta):
            # Convert timedelta to SurrealDB duration format
            seconds = int(value.total_seconds())
            minutes, seconds = divmod(seconds, 60)
            hours, minutes = divmod(minutes, 60)
            days, hours = divmod(hours, 24)

            result = ""
            if days > 0:
                result += f"{days}d"
            if hours > 0:
                result += f"{hours}h"
            if minutes > 0:
                result += f"{minutes}m"
            if seconds > 0 or not result:
                result += f"{seconds}s"

            return Duration.parse(result)

        # If it's already a Duration object, return as is
        if hasattr(value, 'to_string') and hasattr(value, 'elapsed'):
            return value

        raise TypeError(f"Cannot convert {type(value)} to duration")

    def from_db(self, value: Any) -> Optional[datetime.timedelta]:
        """Convert database value to Python timedelta.

        This method converts a SurrealDB duration string from the database to a
        Python timedelta object.

        Args:
            value: The database value to convert

        Returns:
            The Python timedelta object
        """
        if value is not None and isinstance(value, str):
            return self.validate(value)
        return value