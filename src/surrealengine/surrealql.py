"""SurrealQL escaping and formatting utilities.

These helpers provide consistent escaping for identifiers and literals in
SurrealQL strings, reducing the risk of malformed queries and injection.

Notes:
- For literals, we prefer json.dumps for strings, numbers, booleans, nulls.
- For SurrealDB RecordIDs (like table:123 or table:slug), we emit them as-is
  without quotes.
- For dicts that represent records with an 'id' key, we pass through the id
  when it looks like a RecordID.
"""
from __future__ import annotations

import json
import re
import datetime
from typing import Any
from .record_id_utils import RecordIdUtils


try:
    from surrealdb import Datetime
except ImportError:
    Datetime = None

_record_id_re = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*:(?!/)[^\s]+$")


def is_record_id(value: Any) -> bool:
    if isinstance(value, str):
        # Reject URL schemes and whitespace
        if '://' in value or any(ch.isspace() for ch in value):
            return False
        return bool(_record_id_re.match(value))
    try:
        # Some SDKs expose RecordID objects with string repr
        from surrealdb import RecordID  # type: ignore
        return isinstance(value, RecordID)
    except Exception:
        return False


def escape_identifier(name: str) -> str:
    """Escape an identifier (field or table name).

    SurrealQL identifiers are typically safe if they match [A-Za-z_][A-Za-z0-9_]*
    and dotted paths like a.b.c. For safety, we wrap in backticks if it contains
    special characters.
    """
    if re.match(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$", name):
        return name
    # Escape backticks inside by doubling them
    safe = name.replace("`", "``")
    return f"`{safe}`"

def _iso_from_datetime_obj(value: Any) -> str:
    """Extract ISO string from Datetime object or return as-is if string-like."""
    if hasattr(value, 'inner') and isinstance(value.inner, datetime.datetime):
        s = value.inner
    elif hasattr(value, 'dt') and isinstance(value.dt, datetime.datetime):
        s = value.dt
    else:
        # Fallback
        return str(value)
    
    if isinstance(s, datetime.datetime):
        if s.tzinfo is None:
            s = s.replace(tzinfo=datetime.timezone.utc)
        return s.isoformat().replace("+00:00", "Z")
    return str(s)


def escape_literal(value: Any) -> str:
    """Escape a literal value for SurrealQL.

    Handles:
    - Strings/numbers/bools/null via json.dumps (with Surreal datetime literal passthrough)
    - RecordIDs as-unquoted
    - datetime and IsoDateTimeWrapper -> Surreal literal d'...Z'
    - lists/tuples/sets -> recurse
    - dicts: if has 'id' that is a record id, use that; else serialize as map with escaped values
    - Expr: render raw
    """
    # Avoid import cycle: compare by name to tolerate optional import
    try:
        from .expr import Expr  # type: ignore
        if isinstance(value, Expr):
            return str(value)
    except Exception:
        # If Expr cannot be imported here, fall through
        pass

    # RecordID string or object
    if is_record_id(value):
        return str(value)

    # Datetime wrapper
    if Datetime is not None and isinstance(value, Datetime):
        iso = _iso_from_datetime_obj(value)
        # Check if already has d' prefix (unlikely for ISO extract but possible if str fallback)
        if iso.startswith("d'") and iso.endswith("'"):
            return iso
        return f"d'{iso}'"

    # Python datetime
    if isinstance(value, datetime.datetime):
        dt = value if value.tzinfo is not None else value.replace(tzinfo=datetime.timezone.utc)
        iso = dt.isoformat().replace("+00:00", "Z")
        return f"d'{iso}'"

    # Strings: pass Surreal datetime literal through unchanged
    if isinstance(value, str):
        s = value.strip()
        if s.startswith("d'") and s.endswith("'"):
            return s
        return json.dumps(value)

    # dict with 'id' that is a record id
    if isinstance(value, dict) and 'id' in value and is_record_id(value['id']):
        return str(value['id'])

    # collections -> preserve record ids and dt literals
    if isinstance(value, (list, tuple, set)):
        parts = [escape_literal(v) for v in value]
        return f"[{', '.join(parts)}]"

    # General dict: escape each value
    if isinstance(value, dict):
        items = []
        for k, v in value.items():
            items.append(json.dumps(str(k)) + ": " + escape_literal(v))
        return "{" + ", ".join(items) + "}"

    # Fallback: JSON
    return json.dumps(value)
