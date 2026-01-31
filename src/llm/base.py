"""Base LLM interface for different providers."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class FunctionCall(BaseModel):
    """Represents a function call from the LLM."""
    
    name: str = Field(..., description="Name of the function to call")
    arguments: Dict[str, Any] = Field(..., description="Arguments for the function")


class LLMMessage(BaseModel):
    """Represents a message in the LLM conversation."""
    
    role: str = Field(..., description="Role of the message (system, user, assistant, function)")
    content: Optional[str] = Field(default=None, description="Content of the message")
    name: Optional[str] = Field(default=None, description="Name of the function or tool")
    function_call: Optional[FunctionCall] = Field(default=None, description="Function call details")


class LLMResponse(BaseModel):
    """Response from the LLM."""
    
    content: Optional[str] = Field(None, description="Text content of the response")
    function_calls: List[FunctionCall] = Field(default_factory=list, description="Function calls in the response")
    finish_reason: str = Field(..., description="Reason why the generation finished")


class BaseLLM(ABC):
    """Abstract base class for LLM providers."""
    
    def __init__(self, model: str, temperature: float = 0.1, max_tokens: int = 2000):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
    
    @abstractmethod
    async def generate(
        self,
        messages: List[LLMMessage],
        functions: Optional[List[Dict]] = None,
        function_call: Optional[Union[str, Dict]] = None,
    ) -> LLMResponse:
        """
        Generate a response from the LLM.
        
        Args:
            messages: List of messages in the conversation
            functions: List of available functions for function calling
            function_call: Configuration for function calling
            
        Returns:
            LLMResponse object containing the response
        """
        pass
    
    @abstractmethod
    async def generate_with_tools(
        self,
        messages: List[LLMMessage],
        tools: Optional[List[Dict]] = None,
        tool_choice: Optional[Union[str, Dict]] = None,
    ) -> LLMResponse:
        """
        Generate a response with tool calls (OpenAI-style).
        
        Args:
            messages: List of messages in the conversation
            tools: List of available tools
            tool_choice: Configuration for tool choice
            
        Returns:
            LLMResponse object containing the response
        """
        pass
    
    def format_function_for_prompt(self, function: Dict) -> str:
        """
        Format a function definition for inclusion in a prompt.
        
        Args:
            function: Function definition dictionary
            
        Returns:
            Formatted string representation
        """
        name = function.get("name", "")
        description = function.get("description", "")
        parameters = function.get("parameters", {})
        
        param_str = ""
        if parameters:
            props = parameters.get("properties", {})
            required = parameters.get("required", [])
            
            param_lines = []
            for param_name, param_schema in props.items():
                param_type = param_schema.get("type", "any")
                param_desc = param_schema.get("description", "")
                required_marker = " (required)" if param_name in required else ""
                param_lines.append(f"  - {param_name}: {param_type}{required_marker} - {param_desc}")
            
            param_str = "\n" + "\n".join(param_lines)
        
        return f"{name}: {description}{param_str}"
    
    def create_system_message(self, content: str) -> LLMMessage:
        """Create a system message."""
        return LLMMessage(role="system", content=content)
    
    def create_user_message(self, content: str) -> LLMMessage:
        """Create a user message."""
        return LLMMessage(role="user", content=content)
    
    def create_assistant_message(self, content: str) -> LLMMessage:
        """Create an assistant message."""
        return LLMMessage(role="assistant", content=content)
    
    def create_function_message(self, name: str, content: str) -> LLMMessage:
        """Create a function message with function call results."""
        return LLMMessage(role="function", name=name, content=content)
