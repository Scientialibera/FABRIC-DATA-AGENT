"""Dynamic tool loading system for registering service-based tools with LLM agents."""
import json
import inspect
import structlog
from pathlib import Path
from typing import Dict, Any, Callable, Optional
from importlib import import_module

logger = structlog.get_logger(__name__)


def load_tool_configs(config_dir: str = "config/tools") -> Dict[str, Dict[str, Any]]:
    """Load all tool configurations from directory."""
    configs = {}
    config_path = Path(config_dir)
    
    if not config_path.exists():
        return configs
    
    # Look for *.json files (tool configs named after tool)
    for file_path in config_path.glob("*.json"):
        # Tool name is the filename without .json (e.g., fabric_data.json → fabric_data)
        tool_name = file_path.stem
        
        try:
            with open(file_path) as f:
                configs[tool_name] = json.load(f)
        except Exception:
            pass
    
    return configs


def service_name_to_class_name(service_name: str) -> str:
    """Convert snake_case to PascalCaseService."""
    parts = service_name.split("_")
    return "".join(p.capitalize() for p in parts) + "Service"


def get_or_create_service(assistant: Any, service_name: str) -> Optional[Any]:
    """Get service from assistant or create dynamically."""
    service_attr = f"{service_name}_service"
    
    # Check if service already exists on assistant
    if hasattr(assistant, service_attr):
        inst = getattr(assistant, service_attr)
        if inst is not None:
            logger.info("Found pre-initialized service", service_attr=service_attr)
            return inst
    
    # Try to dynamically create service
    try:
        class_name = service_name_to_class_name(service_name)
        module_path = f"src.{service_name}.service"
        
        logger.info("Attempting to load service dynamically", module_path=module_path, class_name=class_name)
        
        module = import_module(module_path)
        
        # Try factory function first
        factory_name = f"get_{service_name}_service"
        factory = getattr(module, factory_name, None)
        if factory:
            logger.info("Found factory function", factory_name=factory_name)
            service_instance = factory()
            logger.info("Created service via factory", service_attr=service_attr)
            return service_instance
        
        # Fall back to class instantiation
        service_class = getattr(module, class_name)
        service_instance = service_class()
        logger.info("Created service via class instantiation", class_name=class_name)
        return service_instance
        
    except Exception as e:
        logger.error("Failed to create service dynamically", 
                    service_name=service_name, 
                    error=str(e),
                    exc_info=True)
        return None


def create_tool_function(
    tool_name: str,
    tool_config: Dict[str, Any],
    service_instance: Any,
    service_method: str = "run"
) -> Callable:
    """Create tool function that calls service method with properly typed parameters."""
    func_cfg = tool_config.get("function", {})
    func_name = func_cfg.get("name", tool_name)
    func_desc = func_cfg.get("description", "")
    params_cfg = func_cfg.get("parameters", {})
    properties = params_cfg.get("properties", {})
    
    # Create docstring with full description
    docstring = func_desc
    if properties:
        docstring += "\n\nParameters:"
        for param_name, param_info in properties.items():
            param_desc = param_info.get("description", "")
            docstring += f"\n  {param_name}: {param_desc}"
    
    # Get parameter names
    param_names = list(properties.keys())
    
    # Use exec to create a function with the exact signature Agent Framework expects
    # This is necessary because we need explicit named parameters, not **kwargs
    
    # Build the function signature
    sig_params = ", ".join(f"{name}: str" for name in param_names)
    
    # Build the tool_call dict construction
    tool_call_items = ", ".join(f'"{name}": {name}' for name in param_names)
    
    func_body = f'''
def {func_name}({sig_params}) -> str:
    """Tool implementation."""
    try:
        tool_call = {{{tool_call_items}}}
        logger.debug("Tool function called", tool_name="{tool_name}", tool_call=tool_call)
        method = getattr(service_instance, service_method)
        result = method(tool_call=tool_call)
        logger.debug("Tool function result", tool_name="{tool_name}", result=result)
        return result
    except Exception as e:
        logger.error("Tool function error", tool_name="{tool_name}", error=str(e), exc_info=True)
        return f"Error: {{str(e)}}"
'''
    
    # Create namespace for exec with necessary imports
    namespace = {
        'logger': logger,
        'getattr': getattr,
        'service_instance': service_instance,
        'service_method': service_method,
    }
    
    # Execute to create the function
    exec(func_body, namespace)
    tool_fn = namespace[func_name]
    
    # Set docstring
    tool_fn.__doc__ = docstring
    tool_fn._params = properties
    
    return tool_fn


def load_and_register_tools(
    assistant: Any,
    config_dir: str = "config",
    service_method: str = "run"
) -> int:
    """Load and register all tools with assistant."""
    if not hasattr(assistant, "tools"):
        return 0
    
    tool_configs = load_tool_configs(config_dir)
    registered = 0
    
    for tool_name, config in tool_configs.items():
        try:
            service = get_or_create_service(assistant, tool_name)
            if not service:
                continue
            
            fn = create_tool_function(tool_name, config, service, service_method)
            assistant.tools.append(fn)
            registered += 1
        except Exception:
            pass
    
    return registered
