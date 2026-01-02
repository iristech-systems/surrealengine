
from typing import List

def split_fields(query_str: str) -> List[str]:
    """
    Split a comma-separated string of fields, respecting parentheses, brackets, and quotes.
    
    Args:
        query_str: The string to split
        
    Returns:
        List of individual field strings
    """
    if not query_str:
        return []
        
    fields = []
    current_field = []
    paren_level = 0
    bracket_level = 0
    brace_level = 0
    in_single_quote = False
    in_double_quote = False
    escaped = False
    
    for char in query_str:
        if escaped:
            current_field.append(char)
            escaped = False
            continue
            
        if char == '\\':
            current_field.append(char)
            escaped = True
            continue
            
        if in_single_quote:
            if char == "'":
                in_single_quote = False
            current_field.append(char)
            continue
            
        if in_double_quote:
            if char == '"':
                in_double_quote = False
            current_field.append(char)
            continue
            
        # Not in string or escaped
        if char == "'":
            in_single_quote = True
            current_field.append(char)
            continue
            
        if char == '"':
            in_double_quote = True
            current_field.append(char)
            continue
            
        if char == '(':
            paren_level += 1
        elif char == ')':
            paren_level = max(0, paren_level - 1)
        elif char == '[':
            bracket_level += 1
        elif char == ']':
            bracket_level = max(0, bracket_level - 1)
        elif char == '{':
            brace_level += 1
        elif char == '}':
            brace_level = max(0, brace_level - 1)
            
        if char == ',' and paren_level == 0 and bracket_level == 0 and brace_level == 0:
            fields.append("".join(current_field).strip())
            current_field = []
        else:
            current_field.append(char)
            
    if current_field:
        fields.append("".join(current_field).strip())
        
    return [f for f in fields if f]


def split_query_on_from(query_str: str) -> tuple[str, str]:
    """
    Split a SQL query into SELECT part and the rest (starting from FROM),
    respecting quotes and parentheses to avoid false positives.
    
    Args:
        query_str: The full query string
        
    Returns:
        Tuple of (select_part, rest_part). 
        If FROM is not found, returns (query_str, "").
    """
    paren_level = 0
    bracket_level = 0
    brace_level = 0
    in_single_quote = False
    in_double_quote = False
    escaped = False
    
    # We look for the sequence " FROM " (case insensitive) outside of quotes/parens
    # Or start of string "FROM " (unlikely for SELECT queries but possible for others)
    # Actually, we iterating char by char, so we can check if we match "FROM" token.
    
    # Simple state machine approach
    
    for i, char in enumerate(query_str):
        if escaped:
            escaped = False
            continue
            
        if char == '\\':
            escaped = True
            continue
            
        if in_single_quote:
            if char == "'":
                in_single_quote = False
            continue
            
        if in_double_quote:
            if char == '"':
                in_double_quote = False
            continue
            
        if char == "'":
            in_single_quote = True
            continue
            
        if char == '"':
            in_double_quote = True
            continue
            
        if char == '(':
            paren_level += 1
        elif char == ')':
            paren_level = max(0, paren_level - 1)
        elif char == '[':
            bracket_level += 1
        elif char == ']':
            bracket_level = max(0, bracket_level - 1)
        elif char == '{':
            brace_level += 1
        elif char == '}':
            brace_level = max(0, brace_level - 1)
            
        # Check if we are potentially at a "FROM" token keywords
        # We need to look ahead slightly. 
        # Token boundary check: prev char is whitespace or start, next char is whitespace or end
        # We only check valid locations (level 0)
        
        if paren_level == 0 and bracket_level == 0 and brace_level == 0:
            if char.upper() == 'F':
                # Check for "FROM"
                # Check boundary before
                valid_boundary_before = (i == 0) or query_str[i-1].isspace() or query_str[i-1] in ')]}'
                if valid_boundary_before:
                    # Check match
                    if query_str[i:i+4].upper() == 'FROM':
                        # Check boundary after
                        after_idx = i + 4
                        valid_boundary_after = (after_idx >= len(query_str)) or query_str[after_idx].isspace() or query_str[after_idx] in '('
                        
                        if valid_boundary_after:
                            # Found it!
                            return query_str[:i].strip(), query_str[i:].strip()
                            
    return query_str, ""

