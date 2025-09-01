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
from typing import Any
from .record_id_utils import RecordIdUtils

_record_id_re = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*:[^\s]+$")


def is_record_id(value: Any) -> bool:
    if isinstance(value, str):
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


def escape_literal(value: Any) -> str:
    """Escape a literal value for SurrealQL.

    - Strings/numbers/bools/null: json.dumps
    - RecordIDs (str like table:id or RecordID objects): unquoted as-is
    - dicts with 'id' that looks like RecordID: use that id
    - lists/tuples/sets: JSON array with each element escaped recursively where
      appropriate (record ids without quotes, others json-dumped)
    - Expr values: render their string representation as-is (used for $vars and raw expressions)
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

    # dict with 'id' that is a record id
    if isinstance(value, dict) and 'id' in value and is_record_id(value['id']):
        return str(value['id'])

    # collections -> try to preserve record ids
    if isinstance(value, (list, tuple, set)):
        parts = [escape_literal(v) for v in value]
        return f"[{', '.join(parts)}]"

    # Fallback: JSON
    return json.dumps(value)
