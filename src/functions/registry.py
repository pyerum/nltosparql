"""Function registry for managing available functions."""

from typing import Dict, List, Optional, Any
from .base import BaseFunction, FunctionResult


class FunctionRegistry:
    """Registry for managing functions that can be called by the LLM."""
    
    def __init__(self, kg_name: str = "wikidata"):
        self._functions: Dict[str, BaseFunction] = {}
        self.kg_name = kg_name
    
    def register(self, function: BaseFunction) -> None:
        """
        Register a function in the registry.
        
        Args:
            function: Function to register
        """
        self._functions[function.name] = function
    
    def unregister(self, function_name: str) -> None:
        """
        Unregister a function from the registry.
        
        Args:
            function_name: Name of the function to unregister
        """
        if function_name in self._functions:
            del self._functions[function_name]
    
    def get_function(self, function_name: str) -> Optional[BaseFunction]:
        """
        Get a function by name.
        
        Args:
            function_name: Name of the function to get
            
        Returns:
            Function object or None if not found
        """
        return self._functions.get(function_name)
    
    def list_functions(self) -> List[str]:
        """
        List all registered function names.
        
        Returns:
            List of function names
        """
        return list(self._functions.keys())
    
    def get_function_definitions(self) -> List[Dict[str, Any]]:
        """
        Get function definitions in LLM format.
        
        Returns:
            List of function definitions as dictionaries
        """
        definitions = []
        for function in self._functions.values():
            definitions.append(function.get_definition().to_dict())
        return definitions
    
    async def execute_function(self, function_name: str, arguments: Dict[str, Any]) -> FunctionResult:
        """
        Execute a function with the given arguments.
        
        Args:
            function_name: Name of the function to execute
            arguments: Arguments to pass to the function
            
        Returns:
            FunctionResult object
        """
        function = self.get_function(function_name)
        if not function:
            return FunctionResult(
                success=False,
                error=f"Function '{function_name}' not found"
            )
        
        # Validate arguments (ignoring kg - it's set by the registry)
        # Remove kg from arguments for validation since it's auto-set by registry
        validation_args = {k: v for k, v in arguments.items() if k != "kg"}
        validation_errors = function.validate_arguments(validation_args)
        if validation_errors:
            return FunctionResult(
                success=False,
                error=f"Argument validation failed: {', '.join(validation_errors)}"
            )
        
        try:
            # Execute the function with kg_name from registry
            result = await function.execute(**arguments, kg=self.kg_name)
            return result
        except Exception as e:
            return FunctionResult(
                success=False,
                error=f"Function execution failed: {str(e)}"
            )
    
    def clear(self) -> None:
        """Clear all registered functions."""
        self._functions.clear()
