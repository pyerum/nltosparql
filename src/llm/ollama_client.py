"""Ollama LLM implementation for local models."""

import json
from typing import Any, Dict, List, Optional, Union
import ollama

from .base import BaseLLM, LLMMessage, LLMResponse, FunctionCall


class OllamaClient(BaseLLM):
    """Ollama LLM client implementation for local models."""
    
    def __init__(
        self,
        model: str = "llama3.1",
        temperature: float = 0.1,
        max_tokens: int = 2000,
        host: Optional[str] = None,
    ):
        super().__init__(model, temperature, max_tokens)
        self.host = host
        
        # Test connection
        try:
            ollama.list()
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Ollama: {e}")
    
    async def generate(
        self,
        messages: List[LLMMessage],
        functions: Optional[List[Dict]] = None,
        function_call: Optional[Union[str, Dict]] = None,
    ) -> LLMResponse:
        """
        Generate a response from Ollama LLM with native tool calling support.
        
        Args:
            messages: List of messages in the conversation
            functions: List of available functions for function calling
            function_call: Configuration for function calling
            
        Returns:
            LLMResponse object containing the response
        """
        # Convert messages to Ollama format
        ollama_messages = []
        for msg in messages:
            if msg.role == 'function':
                # Convert function result to tool message format
                message_dict = {
                    "role": "tool",
                    "tool_name": msg.name,
                    "content": msg.content or ""
                }
            else:
                message_dict = {"role": msg.role, "content": msg.content or ""}
            ollama_messages.append(message_dict)
        
        # Prepare tools for Ollama API
        tools = None
        if functions:
            # Convert functions to Ollama tool format
            tools = []
            for func in functions:
                tool = {
                    "type": "function",
                    "function": {
                        "name": func.get("name", ""),
                        "description": func.get("description", ""),
                        "parameters": func.get("parameters", {})
                    }
                }
                tools.append(tool)
        
        # Prepare request parameters
        params = {
            "model": self.model,
            "messages": ollama_messages,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
            }
        }
        
        # Add tools if available
        if tools:
            params["tools"] = tools
        
        # Make the API call
        try:
            response = ollama.chat(**params)
        except Exception as e:
            raise ConnectionError(f"Ollama API call failed: {e}")
        
        # Extract response content
        content = response.message.content or ""
        
        # Extract tool calls from response
        function_calls = []
        if hasattr(response.message, 'tool_calls') and response.message.tool_calls:
            for tool_call in response.message.tool_calls:
                if hasattr(tool_call, 'function'):
                    function_calls.append(
                        FunctionCall(
                            name=tool_call.function.name,
                            arguments=tool_call.function.arguments
                        )
                    )
        
        return LLMResponse(
            content=content,
            function_calls=function_calls,
            finish_reason="stop",  # Ollama doesn't provide finish reason
        )
    
    
    async def generate_with_tools(
        self,
        messages: List[LLMMessage],
        tools: Optional[List[Dict]] = None,
        tool_choice: Optional[Union[str, Dict]] = None,
    ) -> LLMResponse:
        """
        Generate a response with tool calls.
        
        Args:
            messages: List of messages in the conversation
            tools: List of available tools
            tool_choice: Configuration for tool choice
            
        Returns:
            LLMResponse object containing the response
        """
        # For Ollama, tools are treated the same as functions
        return await self.generate(messages, tools, tool_choice)
