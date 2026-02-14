"""Agent orchestrator for NL-to-SPARQL conversion using function calling."""

import asyncio
import json
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

from ..llm.base import BaseLLM, LLMMessage, LLMResponse, FunctionCall
from ..functions.registry import FunctionRegistry
from ..functions.base import FunctionResult


class AgentOrchestrator:
    """Orchestrates the NL-to-SPARQL conversion process using LLM with function calling."""
    
    def __init__(
        self,
        llm: BaseLLM,
        function_registry: FunctionRegistry,
        max_iterations: int = 20,
        enable_feedback: bool = True,
        max_feedback_loops: int = 2,
        verbose: bool = False
    ):
        self.llm = llm
        self.function_registry = function_registry
        self.max_iterations = max_iterations
        self.enable_feedback = enable_feedback
        self.max_feedback_loops = max_feedback_loops
        self.verbose = verbose
        
        self.conversation_history: List[LLMMessage] = []
        self.function_results: List[Dict[str, Any]] = []
        self.iteration_count = 0
        self.feedback_loops = 0
        
    def _log(self, message: str):
        """Log message if verbose mode is enabled."""
        if self.verbose:
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] {message}")
    
    def _create_system_prompt(self, question: str, kg_name: str) -> str:
        """Create the system prompt for the LLM."""
        # Get available knowledge graphs from config
        import yaml
        import os
        config_path = os.path.join(os.path.dirname(__file__), "../../config/default.yaml")
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        endpoints = config.get('endpoints', {})
        kg_list = ", ".join(endpoints.keys())
        
        prompt = f"""Generate SPARQL queries to answer questions about {kg_name}.
        
When you call a function only include the body of the function in the output, no reasoning or other text.

Available functions:
{self._format_functions_for_prompt()}

Process:
1. Use search_entity to find entities
2. Use discover_properties to find relevant properties
3. Use get_entity_properties to explore entity structure
4. Create SPARQL query
5. Test with execute_query
6. Use answer to provide final result

Question: {question}

Begin by searching for the main entity.
"""
        
        return prompt
    
    def _format_functions_for_prompt(self) -> str:
        """Format function definitions for the prompt."""
        functions = self.function_registry.get_function_definitions()
        formatted = []
        
        for func in functions:
            name = func.get('name', '')
            description = func.get('description', '')
            params = func.get('parameters', {}).get('properties', {})
            required = func.get('parameters', {}).get('required', [])
            
            param_lines = []
            for param_name, param_schema in params.items():
                param_type = param_schema.get('type', 'any')
                param_desc = param_schema.get('description', '')
                required_marker = " (required)" if param_name in required else ""
                param_lines.append(f"    - {param_name}: {param_type}{required_marker} - {param_desc}")
            
            param_str = "\n" + "\n".join(param_lines) if param_lines else ""
            formatted.append(f"{name}: {description}{param_str}")
        
        return "\n\n".join(formatted)
    
    def _format_function_result_for_message(self, function_name: str, result: FunctionResult) -> str:
        """Format function result for inclusion in conversation history."""
        if result.success:
            result_str = json.dumps(result.result, indent=2)
            return f"Function {function_name} succeeded:\n{result_str}"
        else:
            return f"Function {function_name} failed: {result.error}"
    
    async def process_question(
        self,
        question: str,
        kg_name: str = "wikidata"
    ) -> Dict[str, Any]:
        """Process a natural language question and generate SPARQL query."""
        self._log(f"Starting processing of question: {question}")
        self._log(f"Target knowledge graph: {kg_name}")
        
        # Reset state
        self.conversation_history = []
        self.function_results = []
        self.iteration_count = 0
        self.feedback_loops = 0
        
        # Create system prompt
        system_prompt = self._create_system_prompt(question, kg_name)
        self.conversation_history.append(
            LLMMessage(role="system", content=system_prompt)
        )
        
        # Add user question
        self.conversation_history.append(
            LLMMessage(role="user", content=question)
        )
        
        # Main loop
        while self.iteration_count < self.max_iterations:
            self.iteration_count += 1
            self._log(f"Iteration {self.iteration_count}/{self.max_iterations}")
            
            # Get LLM response
            llm_response = await self._get_llm_response()
            
            if not llm_response:
                return self._create_error_result("LLM failed to respond")
            
            # Check for function calls
            if llm_response.function_calls:
                self._log(f"LLM made {len(llm_response.function_calls)} function call(s)")
                
                # Add assistant message with function calls to conversation history
                # This is needed for OpenAI tools API compatibility
                assistant_message = LLMMessage(
                    role="assistant",
                    content=llm_response.content or "",
                    function_call=None
                )
                
                # If there are function calls, add them to the assistant message
                if llm_response.function_calls:
                    # For now, we'll just add the first function call
                    # In a more complete implementation, we'd handle multiple tool calls
                    first_call = llm_response.function_calls[0]
                    assistant_message.function_call = first_call
                
                self.conversation_history.append(assistant_message)
                
                # Execute function calls
                all_successful = True
                for function_call in llm_response.function_calls:
                    function_name = function_call.name
                    arguments = function_call.arguments
                    
                    self._log(f"Executing function: {function_name} with args: {arguments}")
                    
                    # Execute function
                    result = await self.function_registry.execute_function(
                        function_name, arguments
                    )
                    
                    # Record result
                    self.function_results.append({
                        'iteration': self.iteration_count,
                        'function': function_name,
                        'arguments': arguments,
                        'result': result.result if result.success else None,
                        'error': result.error if not result.success else None,
                        'success': result.success
                    })
                    
                    # ADDED: Simple print of function return value
                    if result.success:
                        print(f"\n=== FUNCTION RETURN: {function_name} ===")
                        print(f"Arguments: {arguments}")
                        print(f"Return value: {result.result}")
                        print("=" * 50 + "\n")
                    else:
                        print(f"\n=== FUNCTION ERROR: {function_name} ===")
                        print(f"Arguments: {arguments}")
                        print(f"Error: {result.error}")
                        print("=" * 50 + "\n")
                    
                    # Add function result to conversation
                    result_message = self._format_function_result_for_message(
                        function_name, result
                    )
                    
                    # Use tool_call_id if available (for OpenAI tools API)
                    message_name = function_name
                    if function_call.tool_call_id:
                        message_name = function_call.tool_call_id
                    
                    self.conversation_history.append(
                        LLMMessage(
                            role="function",
                            name=message_name,
                            content=result_message
                        )
                    )
                    
                    # Check if this is an answer or cancel function
                    if function_name == "answer":
                        self._log("Answer function called - process complete")
                        return self._process_answer_result(result)
                    elif function_name == "cancel":
                        self._log("Cancel function called - process complete")
                        return self._process_cancel_result(result)
                    
                    if not result.success:
                        all_successful = False
                        self._log(f"Function {function_name} failed: {result.error}")
                
                # If all functions succeeded, continue
                if all_successful:
                    continue
                else:
                    # Give LLM a chance to recover from function errors
                    continue
            
            # If no function calls, check if we have a text response
            elif llm_response.content:
                # Show more of the reasoning in verbose mode
                if self.verbose:
                    self._log(f"LLM reasoning (full):\n{llm_response.content}")
                else:
                    self._log(f"LLM reasoning: {llm_response.content[:400]}...")
                
                # Add assistant message to history
                self.conversation_history.append(
                    LLMMessage(role="assistant", content=llm_response.content)
                )
                
                # Check if the response seems to be concluding WITHOUT validation
                # We should only prompt for answer if we have validated queries
                has_validated_query = any(
                    f['function'] == 'execute_query' and f['success'] 
                    for f in self.function_results
                )
                
                concluding_keywords = ['final query', 'answer is', 'here is the sparql', 'i conclude', 'the answer']
                if any(keyword in llm_response.content.lower() for keyword in concluding_keywords):
                    if has_validated_query:
                        self._log("LLM appears to be concluding with validated query - prompting for answer function")
                        # Prompt LLM to use answer function
                        self.conversation_history.append(
                            LLMMessage(
                                role="user",
                                content="Please use the answer function to provide the final SPARQL query and answer."
                            )
                        )
                    else:
                        self._log("LLM appears to be concluding WITHOUT validation - prompting to validate first")
                        # Prompt LLM to validate first
                        self.conversation_history.append(
                            LLMMessage(
                                role="user",
                                content="You need to validate your SPARQL query with execute_query before concluding. Please test your query first."
                            )
                        )
            
            # Check for completion conditions
            # Only break if we have no function calls and the LLM seems to be concluding
            if llm_response.finish_reason in ["stop", "length"] and not llm_response.function_calls:
                self._log(f"LLM finished with reason: {llm_response.finish_reason} with no function calls")
                
                # Check if we have validated queries
                has_validated_query = any(
                    f['function'] == 'execute_query' and f['success'] 
                    for f in self.function_results
                )
                
                # Check if the response seems to be concluding
                concluding_keywords = ['final query', 'answer is', 'here is the sparql', 'i conclude', 'i cannot', 'the answer']
                if llm_response.content and any(keyword in llm_response.content.lower() for keyword in concluding_keywords):
                    if has_validated_query:
                        self._log("LLM appears to be concluding with validation - prompting for answer")
                        self.conversation_history.append(
                            LLMMessage(
                                role="user",
                                content="Please use the answer function to provide the final validated SPARQL query and answer."
                            )
                        )
                    else:
                        self._log("LLM appears to be concluding WITHOUT validation - prompting to validate")
                        self.conversation_history.append(
                            LLMMessage(
                                role="user",
                                content="You need to validate your SPARQL query with execute_query before concluding. Please test your query first."
                            )
                        )
                    continue
                else:
                    # LLM stopped but didn't conclude - prompt it to continue
                    self._log("LLM stopped without concluding - prompting to continue")
                    self.conversation_history.append(
                        LLMMessage(
                            role="user",
                            content="Please continue with the next step. If you cannot proceed, use the cancel function."
                        )
                    )
                    continue
        
        # If we reach here, we've exceeded iterations without answer/cancel
        return self._create_timeout_result()
    
    async def _get_llm_response(self) -> Optional[LLMResponse]:
        """Get response from LLM with function calling."""
        try:
            # Get function definitions
            functions = self.function_registry.get_function_definitions()
            
            # Call LLM with function calling
            response = await self.llm.generate(
                messages=self.conversation_history,
                functions=functions,
                function_call="auto"
            )
            
            return response
            
        except Exception as e:
            self._log(f"Error getting LLM response: {e}")
            return None
    
    def _process_answer_result(self, result: FunctionResult) -> Dict[str, Any]:
        """Process result from answer function."""
        if result.success:
            return {
                'status': 'success',
                'result': result.result,
                'iterations': self.iteration_count,
                'function_calls': self.function_results,
                'conversation_history': [
                    msg.dict() for msg in self.conversation_history
                ]
            }
        else:
            return {
                'status': 'error',
                'error': f"Answer function failed: {result.error}",
                'iterations': self.iteration_count,
                'function_calls': self.function_results
            }
    
    def _process_cancel_result(self, result: FunctionResult) -> Dict[str, Any]:
        """Process result from cancel function."""
        if result.success:
            return {
                'status': 'cancelled',
                'result': result.result,
                'iterations': self.iteration_count,
                'function_calls': self.function_results,
                'conversation_history': [
                    msg.dict() for msg in self.conversation_history
                ]
            }
        else:
            return {
                'status': 'error',
                'error': f"Cancel function failed: {result.error}",
                'iterations': self.iteration_count,
                'function_calls': self.function_results
            }
    
    def _create_error_result(self, error: str) -> Dict[str, Any]:
        """Create error result."""
        return {
            'status': 'error',
            'error': error,
            'iterations': self.iteration_count,
            'function_calls': self.function_results
        }
    
    def _create_timeout_result(self) -> Dict[str, Any]:
        """Create timeout result with best possible attempt."""
        # Analyze conversation history to find the best attempt
        best_attempt = None
        best_sparql = None
        best_answer = None
        
        # Look for answer function calls in the results
        for func_call in self.function_results:
            if func_call['function'] == 'answer' and func_call['success']:
                best_attempt = func_call['result']
                if best_attempt:
                    best_sparql = best_attempt.get('sparql')
                    best_answer = best_attempt.get('answer')
                break
        
        # If no answer function was called, look for SPARQL queries in conversation
        if not best_attempt:
            for msg in self.conversation_history:
                if msg.role == 'assistant' and msg.content:
                    # Try to extract SPARQL query from assistant messages
                    content = msg.content
                    # Look for SPARQL patterns
                    import re
                    sparql_patterns = [
                        r'SELECT.*WHERE.*\{.*\}',
                        r'PREFIX.*SELECT',
                        r'CONSTRUCT.*WHERE.*\{.*\}',
                        r'ASK.*WHERE.*\{.*\}'
                    ]
                    
                    for pattern in sparql_patterns:
                        match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
                        if match:
                            best_sparql = match.group(0).strip()
                            # Try to extract answer from surrounding text
                            lines = content.split('\n')
                            for i, line in enumerate(lines):
                                if 'answer' in line.lower() or 'is' in line.lower():
                                    if i + 1 < len(lines):
                                        best_answer = lines[i + 1].strip()
                                    break
                            break
        
        # Also check for any execute_query calls that might have results
        if not best_attempt:
            for func_call in self.function_results:
                if func_call['function'] == 'execute_query' and func_call['success']:
                    result_data = func_call.get('result', {})
                    if result_data.get('results'):
                        best_attempt = {
                            'sparql': func_call.get('arguments', {}).get('query', 'Unknown query'),
                            'results': result_data.get('results', []),
                            'count': result_data.get('count', 0)
                        }
                        best_sparql = best_attempt['sparql']
                        # Try to extract an answer from results
                        if result_data.get('results'):
                            first_result = result_data['results'][0]
                            # Look for any value that might be an answer
                            for key, value in first_result.items():
                                if key not in ['?subject', '?predicate', '?object'] and value:
                                    best_answer = str(value)
                                    break
                        break
        
        timeout_result = {
            'status': 'timeout',
            'error': f"Exceeded maximum iterations ({self.max_iterations})",
            'iterations': self.iteration_count,
            'function_calls': self.function_results,
            'conversation_history': [
                msg.dict() for msg in self.conversation_history
            ]
        }
        
        # Add best attempt if found
        if best_attempt:
            timeout_result['best_attempt'] = best_attempt
            if best_sparql:
                timeout_result['best_sparql'] = best_sparql
            if best_answer:
                timeout_result['best_answer'] = best_answer
        
        return timeout_result
    
    def get_execution_summary(self) -> Dict[str, Any]:
        """Get summary of execution."""
        successful_calls = [f for f in self.function_results if f['success']]
        failed_calls = [f for f in self.function_results if not f['success']]
        
        return {
            'total_iterations': self.iteration_count,
            'total_function_calls': len(self.function_results),
            'successful_function_calls': len(successful_calls),
            'failed_function_calls': len(failed_calls),
            'function_call_breakdown': {
                func_name: len([f for f in self.function_results if f['function'] == func_name])
                for func_name in set(f['function'] for f in self.function_results)
            }
        }
