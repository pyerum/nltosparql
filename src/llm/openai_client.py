"""OpenAI LLM implementation."""

import json
from typing import Any, Dict, List, Optional, Union
from openai import AsyncOpenAI

from .base import BaseLLM, LLMMessage, LLMResponse, FunctionCall


class OpenAIClient(BaseLLM):
    """OpenAI LLM client implementation."""
    
    def __init__(
        self,
        model: str = "gpt-4o",
        temperature: float = 0.1,
        max_tokens: int = 2000,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        super().__init__(model, temperature, max_tokens)
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    
    async def generate(
        self,
        messages: List[LLMMessage],
        functions: Optional[List[Dict]] = None,
        function_call: Optional[Union[str, Dict]] = None,
    ) -> LLMResponse:
        """
        Generate a response from OpenAI LLM.
        
        Args:
            messages: List of messages in the conversation
            functions: List of available functions for function calling
            function_call: Configuration for function calling
            
        Returns:
            LLMResponse object containing the response
        """
        # Check if we should use tools instead of functions (for OpenRouter)
        # OpenRouter requires tools instead of functions
        if functions and self._should_use_tools():
            # Convert functions to tools format
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
            
            # Convert function_call to tool_choice
            tool_choice = None
            if function_call:
                if isinstance(function_call, str):
                    tool_choice = function_call
                elif isinstance(function_call, dict):
                    tool_choice = function_call
            
            # Use the tools API
            return await self.generate_with_tools(
                messages=messages,
                tools=tools,
                tool_choice=tool_choice
            )
        
        # Otherwise use the old functions API
        # Convert messages to OpenAI format
        openai_messages = []
        for msg in messages:
            message_dict: Dict[str, Any] = {"role": msg.role}
            if msg.content:
                message_dict["content"] = msg.content
            if msg.name:
                message_dict["name"] = msg.name
            if msg.function_call:
                message_dict["function_call"] = {
                    "name": msg.function_call.name,
                    "arguments": json.dumps(msg.function_call.arguments),
                }
            openai_messages.append(message_dict)
        
        # Prepare request parameters
        params = {
            "model": self.model,
            "messages": openai_messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        
        if functions:
            params["functions"] = functions
        if function_call:
            params["function_call"] = function_call
        
        # Make the API call
        response = await self.client.chat.completions.create(**params)
        
        # Extract response content and function calls
        choice = response.choices[0]
        message = choice.message
        
        function_calls = []
        if message.function_call:
            try:
                arguments = json.loads(message.function_call.arguments)
            except json.JSONDecodeError:
                arguments = {}
            
            function_calls.append(
                FunctionCall(
                    name=message.function_call.name,
                    arguments=arguments,
                )
            )
        
        return LLMResponse(
            content=message.content,
            function_calls=function_calls,
            finish_reason=choice.finish_reason or "stop",
        )
    
    def _should_use_tools(self) -> bool:
        """
        Check if we should use tools API instead of functions API.
        
        Returns:
            True if we should use tools API (for OpenRouter)
        """
        # Check if base_url contains openrouter.ai
        if hasattr(self.client, 'base_url') and self.client.base_url:
            return 'openrouter.ai' in str(self.client.base_url)
        
        # Check if model name suggests OpenRouter
        openrouter_models = ['deepseek/deepseek', 'openrouter/', 'anthropic/', 'google/']
        for model_prefix in openrouter_models:
            if model_prefix in self.model:
                return True
        
        return False
    
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
        # Convert messages to OpenAI format
        openai_messages = []
        for msg in messages:
            message_dict: Dict[str, Any] = {}
            
            # For tool messages, we need to convert role from "function" to "tool"
            if msg.role == "function":
                message_dict["role"] = "tool"
                # Try to extract tool_call_id from name or generate one
                if msg.name and msg.name.startswith("call_"):
                    message_dict["tool_call_id"] = msg.name
                else:
                    message_dict["tool_call_id"] = f"call_{msg.name}"
                message_dict["content"] = msg.content or ""
            else:
                message_dict["role"] = msg.role
                if msg.content:
                    message_dict["content"] = msg.content
                if msg.name:
                    message_dict["name"] = msg.name
            
            # Handle tool calls from assistant messages
            if msg.function_call:
                # Generate a unique tool call ID
                import uuid
                tool_call_id = f"call_{uuid.uuid4().hex[:8]}"
                
                # Convert function call to tool call for OpenAI
                message_dict["tool_calls"] = [{
                    "id": tool_call_id,
                    "type": "function",
                    "function": {
                        "name": msg.function_call.name,
                        "arguments": json.dumps(msg.function_call.arguments),
                    }
                }]
                
                # Store the tool call ID in the message name for later reference
                message_dict["name"] = tool_call_id
            
            openai_messages.append(message_dict)
        
        # Prepare request parameters
        params = {
            "model": self.model,
            "messages": openai_messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        
        if tools:
            params["tools"] = tools
        if tool_choice:
            params["tool_choice"] = tool_choice
        
        # Make the API call
        response = await self.client.chat.completions.create(**params)
        
        # Extract response content and tool calls
        choice = response.choices[0]
        message = choice.message
        
        function_calls = []
        if message.tool_calls:
            for tool_call in message.tool_calls:
                if tool_call.type == "function":
                    try:
                        arguments = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        arguments = {}
                    
                    function_calls.append(
                        FunctionCall(
                            name=tool_call.function.name,
                            arguments=arguments,
                            tool_call_id=tool_call.id  # Store the tool call ID
                        )
                    )
        
        return LLMResponse(
            content=message.content,
            function_calls=function_calls,
            finish_reason=choice.finish_reason or "stop",
        )
