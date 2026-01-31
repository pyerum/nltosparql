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
            message_dict = {"role": msg.role}
            if msg.content:
                message_dict["content"] = msg.content
            if msg.name:
                message_dict["name"] = msg.name
            if msg.function_call:
                # Convert function call to tool call for OpenAI
                message_dict["tool_calls"] = [{
                    "id": f"call_{msg.function_call.name}",
                    "type": "function",
                    "function": {
                        "name": msg.function_call.name,
                        "arguments": json.dumps(msg.function_call.arguments),
                    }
                }]
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
                        )
                    )
        
        return LLMResponse(
            content=message.content,
            function_calls=function_calls,
            finish_reason=choice.finish_reason or "stop",
        )
