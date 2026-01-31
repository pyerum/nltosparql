"""Base classes for function calling system."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class FunctionParameter(BaseModel):
    """Parameter definition for a function."""
    
    name: str = Field(..., description="Name of the parameter")
    type: str = Field(..., description="Type of the parameter (string, integer, etc.)")
    description: str = Field(..., description="Description of the parameter")
    required: bool = Field(default=True, description="Whether the parameter is required")


class FunctionDefinition(BaseModel):
    """Definition of a function that can be called by the LLM."""
    
    name: str = Field(..., description="Name of the function")
    description: str = Field(..., description="Description of what the function does")
    parameters: List[FunctionParameter] = Field(default_factory=list, description="List of parameters")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert function definition to dictionary format for LLM."""
        properties = {}
        required = []
        
        for param in self.parameters:
            properties[param.name] = {
                "type": param.type,
                "description": param.description,
            }
            if param.required:
                required.append(param.name)
        
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            }
        }


class FunctionResult(BaseModel):
    """Result of a function execution."""
    
    success: bool = Field(..., description="Whether the function executed successfully")
    result: Any = Field(default=None, description="Result of the function execution")
    error: Optional[str] = Field(default=None, description="Error message if execution failed")


class BaseFunction(ABC):
    """Abstract base class for functions that can be called by the LLM."""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
    
    @abstractmethod
    async def execute(self, **kwargs) -> FunctionResult:
        """
        Execute the function with the given arguments.
        
        Args:
            **kwargs: Arguments passed to the function
            
        Returns:
            FunctionResult object containing the result
        """
        pass
    
    @abstractmethod
    def get_definition(self) -> FunctionDefinition:
        """
        Get the function definition for the LLM.
        
        Returns:
            FunctionDefinition object
        """
        pass
    
    def validate_arguments(self, arguments: Dict[str, Any]) -> List[str]:
        """
        Validate function arguments.
        
        Args:
            arguments: Dictionary of arguments to validate
            
        Returns:
            List of error messages, empty if valid
        """
        errors = []
        definition = self.get_definition()
        
        # Check required parameters
        for param in definition.parameters:
            if param.required and param.name not in arguments:
                errors.append(f"Missing required parameter: {param.name}")
        
        # Check for unknown parameters
        for arg_name in arguments.keys():
            if arg_name not in [p.name for p in definition.parameters]:
                errors.append(f"Unknown parameter: {arg_name}")
        
        return errors
