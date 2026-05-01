"""
Tool registry system for Voice Live function calling.

Provides decorators and utilities for registering, discovering, and executing tools
that can be called by Voice Live agents.
"""

import inspect
import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Global tool registry
_TOOL_REGISTRY: Dict[str, Callable] = {}
_TOOL_SCHEMAS: Dict[str, Dict[str, Any]] = {}


def register_tool(
    name: Optional[str] = None,
    description: Optional[str] = None,
    parameters: Optional[Dict[str, Any]] = None,
):
    """
    Decorator to register a function as a Voice Live tool.

    Args:
        name: Tool name (defaults to function name)
        description: Tool description
        parameters: JSON Schema for parameters

    Example:
        @register_tool(
            description="Get customer information by ID",
            parameters={
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string", "description": "Customer ID"}
                },
                "required": ["customer_id"]
            }
        )
        async def get_customer(customer_id: str) -> dict:
            return {"id": customer_id, "name": "John Doe"}
    """

    def decorator(func: Callable) -> Callable:
        tool_name = name or func.__name__
        tool_description = description or func.__doc__ or f"Execute {tool_name}"

        # Generate parameter schema from function signature if not provided
        if parameters is None:
            sig = inspect.signature(func)
            props = {}
            required = []

            for param_name, param in sig.parameters.items():
                if param_name in ("self", "cls"):
                    continue

                param_type = "string"  # Default type
                if param.annotation != inspect.Parameter.empty:
                    type_map = {
                        str: "string",
                        int: "integer",
                        float: "number",
                        bool: "boolean",
                        dict: "object",
                        list: "array",
                    }
                    param_type = type_map.get(param.annotation, "string")

                props[param_name] = {"type": param_type}

                if param.default == inspect.Parameter.empty:
                    required.append(param_name)

            tool_parameters = {
                "type": "object",
                "properties": props,
                "required": required,
            }
        else:
            tool_parameters = parameters

        # Build tool schema
        schema = {
            "type": "function",
            "function": {
                "name": tool_name,
                "description": tool_description,
                "parameters": tool_parameters,
            },
        }

        # Register the tool
        _TOOL_REGISTRY[tool_name] = func
        _TOOL_SCHEMAS[tool_name] = schema

        logger.debug(f"Registered tool: {tool_name}")

        return func

    return decorator


def get_tool(name: str) -> Optional[Callable]:
    """
    Get a registered tool by name.

    Args:
        name: Tool name

    Returns:
        Tool function or None if not found
    """
    return _TOOL_REGISTRY.get(name)


def get_tool_schemas() -> List[Dict[str, Any]]:
    """
    Get all registered tool schemas.

    Returns:
        List of tool schemas in OpenAI function calling format
    """
    return list(_TOOL_SCHEMAS.values())


def list_tools() -> List[str]:
    """
    List all registered tool names.

    Returns:
        List of tool names
    """
    return list(_TOOL_REGISTRY.keys())


async def execute_tool(
    name: str,
    arguments: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Execute a registered tool by name.

    Args:
        name: Tool name
        arguments: Tool arguments

    Returns:
        Tool execution result

    Raises:
        ValueError: If tool not found
        Exception: If tool execution fails
    """
    tool = get_tool(name)

    if tool is None:
        raise ValueError(f"Tool not found: {name}")

    try:
        logger.info(f"Executing tool: {name} with args: {arguments}")

        # Execute the tool (handle both sync and async functions)
        if inspect.iscoroutinefunction(tool):
            result = await tool(**arguments)
        else:
            result = tool(**arguments)

        logger.info(f"Tool {name} executed successfully")

        # Ensure result is serializable
        if not isinstance(result, (dict, list, str, int, float, bool, type(None))):
            result = {"result": str(result)}

        return {"success": True, "result": result}

    except Exception as e:
        logger.error(f"Error executing tool {name}: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


def clear_registry() -> None:
    """Clear all registered tools (useful for testing)."""
    _TOOL_REGISTRY.clear()
    _TOOL_SCHEMAS.clear()
    logger.debug("Cleared tool registry")


class ToolRegistry:
    """
    Context manager for isolated tool registries.

    Useful for testing or when you need multiple independent registries.
    """

    def __init__(self):
        self.tools: Dict[str, Callable] = {}
        self.schemas: Dict[str, Dict[str, Any]] = {}

    def register(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ):
        """Register a tool in this isolated registry."""

        def decorator(func: Callable) -> Callable:
            tool_name = name or func.__name__
            tool_description = description or func.__doc__ or f"Execute {tool_name}"

            if parameters is None:
                sig = inspect.signature(func)
                props = {}
                required = []

                for param_name, param in sig.parameters.items():
                    if param_name in ("self", "cls"):
                        continue

                    props[param_name] = {"type": "string"}

                    if param.default == inspect.Parameter.empty:
                        required.append(param_name)

                tool_parameters = {
                    "type": "object",
                    "properties": props,
                    "required": required,
                }
            else:
                tool_parameters = parameters

            schema = {
                "type": "function",
                "function": {
                    "name": tool_name,
                    "description": tool_description,
                    "parameters": tool_parameters,
                },
            }

            self.tools[tool_name] = func
            self.schemas[tool_name] = schema

            return func

        return decorator

    def get_schemas(self) -> List[Dict[str, Any]]:
        """Get all tool schemas in this registry."""
        return list(self.schemas.values())

    async def execute(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool in this registry."""
        tool = self.tools.get(name)

        if tool is None:
            raise ValueError(f"Tool not found: {name}")

        try:
            if inspect.iscoroutinefunction(tool):
                result = await tool(**arguments)
            else:
                result = tool(**arguments)

            if not isinstance(result, (dict, list, str, int, float, bool, type(None))):
                result = {"result": str(result)}

            return {"success": True, "result": result}

        except Exception as e:
            logger.error(f"Error executing tool {name}: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
