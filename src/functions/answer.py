"""Answer and cancellation functions."""

from typing import Dict, Any, Optional
from .base import BaseFunction, FunctionDefinition, FunctionParameter, FunctionResult


class AnswerFunction(BaseFunction):
    """Provide final answer with SPARQL query."""
    
    def __init__(self):
        super().__init__(
            name="answer",
            description="Provide the final SPARQL query and answer to the question"
        )
    
    def get_definition(self) -> FunctionDefinition:
        return FunctionDefinition(
            name=self.name,
            description=self.description,
            parameters=[
                FunctionParameter(
                    name="kg",
                    type="string",
                    description="Knowledge graph name",
                    required=True
                ),
                FunctionParameter(
                    name="sparql",
                    type="string",
                    description="Final SPARQL query",
                    required=True
                ),
                FunctionParameter(
                    name="answer",
                    type="string",
                    description="Human-readable answer to the question",
                    required=True
                ),
                FunctionParameter(
                    name="explanation",
                    type="string",
                    description="Explanation of how the query answers the question",
                    required=False
                )
            ]
        )
    
    async def execute(self, **kwargs) -> FunctionResult:
        kg = kwargs.get("kg")
        sparql = kwargs.get("sparql")
        answer = kwargs.get("answer")
        explanation = kwargs.get("explanation", "")
        
        if not kg or not sparql or not answer:
            return FunctionResult(
                success=False,
                error="Missing required parameters: kg, sparql, and answer"
            )
        
        return FunctionResult(
            success=True,
            result={
                'knowledge_graph': kg,
                'sparql_query': sparql,
                'answer': answer,
                'explanation': explanation,
                'status': 'completed'
            }
        )


class CancelFunction(BaseFunction):
    """Cancel the generation process with explanation."""
    
    def __init__(self):
        super().__init__(
            name="cancel",
            description="Cancel the generation process when no satisfactory SPARQL query can be found"
        )
    
    def get_definition(self) -> FunctionDefinition:
        return FunctionDefinition(
            name=self.name,
            description=self.description,
            parameters=[
                FunctionParameter(
                    name="explanation",
                    type="string",
                    description="Explanation of why no satisfactory query could be found",
                    required=True
                ),
                FunctionParameter(
                    name="best_attempt",
                    type="object",
                    description="Best attempt at a SPARQL query (optional)",
                    required=False
                )
            ]
        )
    
    async def execute(self, **kwargs) -> FunctionResult:
        explanation = kwargs.get("explanation")
        best_attempt = kwargs.get("best_attempt")
        
        if not explanation:
            return FunctionResult(
                success=False,
                error="Missing required parameter: explanation"
            )
        
        result = {
            'status': 'cancelled',
            'explanation': explanation
        }
        
        if best_attempt:
            result['best_attempt'] = best_attempt
        
        return FunctionResult(
            success=True,
            result=result
        )
