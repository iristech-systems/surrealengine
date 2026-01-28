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

def surreal_func(name: str, args: Optional[List[Tuple[str, str]]] = None, return_type: Optional[str] = None, permissions: str = "FULL", body: Optional[str] = None):
    """
    Decorator to define a SurrealDB function.

    Args:
        name: The name of the function in SurrealDB (e.g., "fn::greet")
        args: List of (argument_name, type) tuples. If None, inferred from type hints.
        return_type: The return type of the function. If None, inferred from type hints.
        permissions: Permissions for the function (default: "FULL")
        body: The JavaScript body of the function. If None, the function's docstring is used.
    """
    def decorator(func):
        nonlocal args, return_type, body

        # Infer args and return_type from type hints if not provided
        if args is None or return_type is None:
            import inspect
            sig = inspect.signature(func)
            
            # Helper to map python types to surreal types
            def map_type(py_type):
                if py_type is str: return "string"
                if py_type is int: return "int"
                if py_type is float: return "float"
                if py_type is bool: return "bool"
                if py_type is list or getattr(py_type, '__origin__', None) is list: return "array"
                if py_type is dict or getattr(py_type, '__origin__', None) is dict: return "object"
                # Fallback for now
                return "any"

            if args is None:
                args = []
                for param_name, param in sig.parameters.items():
                    if param.annotation != inspect.Parameter.empty:
                        s_type = map_type(param.annotation)
                        args.append((param_name, s_type))
                    else:
                        args.append((param_name, "any"))

            if return_type is None:
                if sig.return_annotation != inspect.Signature.empty:
                    if sig.return_annotation is None:
                        return_type = "null" # or use option<none> behavior?
                    else:
                        return_type = map_type(sig.return_annotation)
                else:
                    return_type = "any"

        func_body = body
        if func_body is None:
             # Use docstring as body
             if func.__doc__:
                 func_body = func.__doc__
             else:
                 raise ValueError(f"Function {name} must have a body or docstring defined.")

        # Cleanup body indentation
        func_body = textwrap.dedent(func_body).strip()
        
        # Ensure body starts with { and ends with }
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

def generate_function_statements() -> List[str]:
    """Generate SQL statements for all registered functions."""
    return [fn.to_sql() for fn in _function_registry]
