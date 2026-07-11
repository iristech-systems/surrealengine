import datetime
from typing import Any, Optional



from .base import Field

class DateTimeField(Field):
    """DateTime field type.

    This field type stores datetime values and provides validation and
    conversion between Python datetime objects and SurrealDB datetime format.

    SurrealDB v2.0.0+ requires datetime values to have a ``d`` prefix or be cast
    as <datetime>. This field handles the conversion automatically, so you can
    use standard Python datetime objects in your code.

    Example::

        class Event(Document):
            created_at = DateTimeField(default=datetime.datetime.now)
            scheduled_for = DateTimeField()

        # Python datetime objects are automatically converted to SurrealDB format
        event = Event(scheduled_for=datetime.datetime.now() + datetime.timedelta(days=7))
        await event.save()
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

        Accepts datetime, Datetime, ISO strings (with optional Z or space separator),
        Surreal d'...' literals, and epoch seconds/milliseconds (int/float).
        """
        value = super().validate(value)
        if value is None:
            return None

        # Already a datetime
        if isinstance(value, datetime.datetime):
            return value

        # SDK wrapper instance provided directly
        try:
            from surrealdb import Datetime
            if isinstance(value, Datetime):
                # Assuming Datetime has a 'dt' or 'datetime' property or similar,
                # or we can extract it. Based on SDK source, it wraps valid input.
                # If it stores it as string internally or object, we need to extract.
                # For now, let's assume we can trust it or it has a way to get back to datetime.
                # If the SDK 1.0.7 Datetime object usage is opaque, we might return it as is
                # if the expected return type was lenient, but type hint says Optional[datetime.datetime].
                # We should try to extract the python datetime.
                if hasattr(value, 'inner'): # Check SDK source if possible, else generic
                    return value.inner
                if hasattr(value, 'dt'):
                    return value.dt
                # Fallback: maybe it is a subclass of datetime? Unlikely.
                # If we return it here, it breaks return type contract if it's not a datetime.
                # Let's assume validation is satisfied if it's a Datetime, but we need to return datetime. 
                # Let's inspect it via str and parse if needed.
                return datetime.datetime.fromisoformat(str(value).replace("d'", "").replace("'", "").replace('Z', '+00:00'))
        except ImportError:
            pass

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
        if value is None:
            return None

        if isinstance(value, str):
            try:
                value = datetime.datetime.fromisoformat(value.replace('Z', '+00:00'))
            except ValueError:
                return value

        if isinstance(value, (int, float)):
            seconds = value / 1000.0 if value >= 1_000_000_000_000 else float(value)
            try:
                value = datetime.datetime.fromtimestamp(seconds, tz=datetime.timezone.utc)
            except Exception:
                return value

        if isinstance(value, datetime.datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=datetime.timezone.utc)
            return f"d'{value.isoformat().replace('+00:00','Z')}'"

        try:
            from surrealdb import Datetime
            if isinstance(value, Datetime):
                if hasattr(value, 'dt') and hasattr(value.dt, 'isoformat'):
                    return f"d'{value.dt.isoformat().replace('+00:00','Z')}'"
                return str(value)
        except ImportError:
            pass

        return value

    def from_db(self, value: Any) -> Optional[datetime.datetime]:
        """Convert database value to Python datetime.

        Accepts Datetime, Surreal d'...' literal strings, ISO strings (with optional Z),
        or datetime instances. Returns a Python datetime (timezone-aware if source has offset).
        """
        if value is None:
            return None
        
        try:
            from surrealdb import Datetime
            # SDK wrapper
            if isinstance(value, Datetime):
                # Try to extract the datetime object
                if hasattr(value, 'inner') and isinstance(value.inner, datetime.datetime):
                    return value.inner
                if hasattr(value, 'dt') and isinstance(value.dt, datetime.datetime):
                    return value.dt
                # Fallback to string parsing if wrapper attributes unknown
                s = str(value)
                if s.startswith("d'") and s.endswith("'"):
                    s = s[2:-1]
                try:
                    return datetime.datetime.fromisoformat(s.replace('Z', '+00:00'))
                except ValueError:
                    return None
        except ImportError:
            pass
            
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
        try:
            from surrealdb import Duration
        except ImportError:
            Duration = None
        self.py_type = (datetime.timedelta, Duration) if Duration is not None else datetime.timedelta

    def validate(self, value: Any) -> Optional[datetime.timedelta]:
        value = super().validate(value)
        if value is not None:
            if isinstance(value, datetime.timedelta):
                return value

            _Duration = self._get_duration_class()
            if _Duration is not None and isinstance(value, _Duration):
                if isinstance(value.elapsed, (int, float)):
                    return datetime.timedelta(seconds=value.elapsed / 1_000_000_000)
                return self.validate(str(value))

            if isinstance(value, str):
                if _Duration is not None:
                    try:
                        dur = _Duration.parse(value)
                        if isinstance(dur.elapsed, (int, float)):
                            return datetime.timedelta(seconds=dur.elapsed / 1_000_000_000)
                    except ValueError:
                        pass
                parts = value.replace(',', '').split()
                total = 0.0
                import re as _re
                for part in parts:
                    m = _re.match(r'(\d+)\s*([wdhms]?)', part)
                    if m:
                        n = int(m.group(1))
                        u = m.group(2) or 's'
                        mul = {'w': 604800, 'd': 86400, 'h': 3600, 'm': 60, 's': 1}.get(u, 1)
                        total += n * mul
                if total > 0:
                    return datetime.timedelta(seconds=total)

            raise TypeError(f"Expected duration for field '{self.name}', got {type(value)}")
        return value

    @staticmethod
    def _get_duration_class():
        try:
            from surrealdb import Duration
            return Duration
        except ImportError:
            return None

    @staticmethod
    def _duration_to_str(dur) -> str:
        if hasattr(dur, "to_string"):
            return dur.to_string()
        return str(dur)

    def to_db(self, value: Any) -> Optional[Any]:
        if value is None:
            return None

        if isinstance(value, str):
            self.validate(value)
            if 'y' in value:
                import re
                year_match = re.search(r'(\d+)y', value)
                if year_match:
                    years = int(year_match.group(1))
                    days = years * 365
                    value = re.sub(r'\d+y', f'{days}d', value)
            return value

        if isinstance(value, datetime.timedelta):
            total_seconds = int(value.total_seconds())
            parts = []
            for unit, secs in [("w", 604800), ("d", 86400), ("h", 3600), ("m", 60), ("s", 1)]:
                if total_seconds >= secs:
                    count = total_seconds // secs
                    parts.append(f"{count}{unit}")
                    total_seconds -= count * secs
            return "".join(parts) if parts else "0s"

        _Duration = self._get_duration_class()
        if _Duration is not None and isinstance(value, _Duration):
            return self._duration_to_str(value)

        raise TypeError(f"Cannot convert {type(value)} to duration")

    def from_db(self, value: Any) -> Optional[datetime.timedelta]:
        if value is not None:
            return self.validate(value)
        return value