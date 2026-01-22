from dataclasses import dataclass
from typing import List, Tuple, Optional, Callable
import textwrap

@dataclass
class SurrealFunction:
    """Metadata for a SurrealDB function."""
    name: str
    args: List[Tuple[str, str]]  # List of (name, type) tuples
    return_type: str
    body: str
    permissions: str = "FULL"
    entry_point: Optional[Callable] = None  # The Python function decorated

    def to_sql(self) -> str:
        """Generate the DEFINE FUNCTION statement."""
        arg_str = ", ".join([f"${name}: {typ}" for name, typ in self.args])
        
        # Format body to be safe? 
        # SurrealDB functions use curly braces block.
        # NOTE: 'RETURNS type' syntax seems to cause parse error in current DB version (Expected '{').
        # So we omit it for now.
        return f"DEFINE FUNCTION {self.name}({arg_str}) {self.body};"

# Global registry
_function_registry: List[SurrealFunction] = []

def surreal_func(name: str, args: List[Tuple[str, str]], return_type: str, permissions: str = "FULL", body: Optional[str] = None):
    """
    Decorator to define a SurrealDB function.

    Args:
        name: The name of the function in SurrealDB (e.g., "fn::greet")
        args: List of (argument_name, type) tuples (e.g., [("name", "string")])
        return_type: The return type of the function (e.g., "string")
        permissions: Permissions for the function (default: "FULL")
        body: The JavaScript body of the function. If None, we might eventually support transpilation, 
              but for now explicit body is required or we expect the user to provide it.
              Actually, let's enforce body for v1.
    """
    def decorator(func):
        # If body is not provided, maybe we can read docstring? 
        # For now, let's require explicit body or we can check docstring if body is None
        func_body = body
        if func_body is None:
             raise ValueError(f"Function {name} must have a 'body' argument defined.")

        # Cleanup body indentation
        func_body = textwrap.dedent(func_body).strip()
        
        # Ensure body starts with { and ends with } if not provided?
        # SurrealDB CREATE FUNCTION syntax: ... { return "..." };
        # If user provides just the code "return 1;", we should wrap it.
        if not func_body.startswith("{"):
            func_body = "{\n" + textwrap.indent(func_body, "    ") + "\n}"

        fn_meta = SurrealFunction(
            name=name,
            args=args,
            return_type=return_type,
            body=func_body,
            permissions=permissions,
            entry_point=func
        )
        _function_registry.append(fn_meta)
        return func
    return decorator

def get_registered_functions() -> List[SurrealFunction]:
    return _function_registry
