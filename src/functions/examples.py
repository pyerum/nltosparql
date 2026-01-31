"""Example-based learning functions for SPARQL query generation."""

from typing import Dict, List, Optional, Any
from .base import BaseFunction, FunctionDefinition, FunctionParameter, FunctionResult


class GetSimilarExamplesFunction(BaseFunction):
    """Get similar example SPARQL queries for a given question."""
    
    def __init__(self):
        super().__init__(
            name="get_similar_examples",
            description="Get similar example SPARQL queries and their patterns for a given question"
        )
        # In a real implementation, this would connect to a database or cache
        # For now, we'll use a simple in-memory store
        self._examples = self._load_example_queries()
    
    def _load_example_queries(self) -> List[Dict[str, Any]]:
        """Load example SPARQL queries."""
        # These are simplified examples - in production, you'd have many more
        # and they'd be stored in a database or file
        return [
            {
                'question': 'What is the capital of France?',
                'sparql': """
                PREFIX wd: <http://www.wikidata.org/entity/>
                PREFIX wdt: <http://www.wikidata.org/prop/direct/>
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                
                SELECT ?capital ?capitalLabel WHERE {
                  wd:Q142 wdt:P36 ?capital .
                  ?capital rdfs:label ?capitalLabel .
                  FILTER(LANG(?capitalLabel) = "en")
                }
                """,
                'entities': ['wd:Q142'],  # France
                'properties': ['wdt:P36'],  # capital property
                'patterns': ['entity-property-value'],
                'description': 'Find property value of an entity'
            },
            {
                'question': 'Who is the author of "The Great Gatsby"?',
                'sparql': """
                PREFIX wd: <http://www.wikidata.org/entity/>
                PREFIX wdt: <http://www.wikidata.org/prop/direct/>
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                
                SELECT ?author ?authorLabel WHERE {
                  ?book wdt:P1476 "The Great Gatsby"@en .
                  ?book wdt:P50 ?author .
                  ?author rdfs:label ?authorLabel .
                  FILTER(LANG(?authorLabel) = "en")
                }
                """,
                'entities': [],
                'properties': ['wdt:P1476', 'wdt:P50'],  # title, author
                'patterns': ['literal-property-entity'],
                'description': 'Find entity by literal value then follow property'
            },
            {
                'question': 'Which countries border Germany?',
                'sparql': """
                PREFIX wd: <http://www.wikidata.org/entity/>
                PREFIX wdt: <http://www.wikidata.org/prop/direct/>
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                
                SELECT ?country ?countryLabel WHERE {
                  wd:Q183 wdt:P47 ?country .
                  ?country rdfs:label ?countryLabel .
                  FILTER(LANG(?countryLabel) = "en")
                }
                """,
                'entities': ['wd:Q183'],  # Germany
                'properties': ['wdt:P47'],  # shares border with
                'patterns': ['entity-property-entity'],
                'description': 'Find related entities via property'
            },
            {
                'question': 'What is the population of Tokyo?',
                'sparql': """
                PREFIX wd: <http://www.wikidata.org/entity/>
                PREFIX wdt: <http://www.wikidata.org/prop/direct/>
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                
                SELECT ?population WHERE {
                  wd:Q1490 wdt:P1082 ?population .
                }
                """,
                'entities': ['wd:Q1490'],  # Tokyo
                'properties': ['wdt:P1082'],  # population
                'patterns': ['entity-property-literal'],
                'description': 'Find literal property value'
            }
        ]
    
    def _calculate_similarity(self, question: str, example_question: str) -> float:
        """Calculate similarity between two questions."""
        # Simple word overlap similarity
        question_words = set(question.lower().split())
        example_words = set(example_question.lower().split())
        
        if not question_words or not example_words:
            return 0.0
        
        intersection = question_words.intersection(example_words)
        union = question_words.union(example_words)
        
        return len(intersection) / len(union)
    
    def get_definition(self) -> FunctionDefinition:
        return FunctionDefinition(
            name=self.name,
            description=self.description,
            parameters=[
                FunctionParameter(
                    name="question",
                    type="string",
                    description="Question to find similar examples for",
                    required=True
                ),
                FunctionParameter(
                    name="kg",
                    type="string",
                    description="Knowledge graph name (e.g., 'wikidata')",
                    required=True
                ),
                FunctionParameter(
                    name="limit",
                    type="integer",
                    description="Maximum number of examples to return (default: 3)",
                    required=False
                ),
                FunctionParameter(
                    name="min_similarity",
                    type="number",
                    description="Minimum similarity score (0.0 to 1.0, default: 0.3)",
                    required=False
                )
            ]
        )
    
    async def execute(self, **kwargs) -> FunctionResult:
        question = kwargs.get("question")
        kg = kwargs.get("kg")
        limit = kwargs.get("limit", 3)
        min_similarity = kwargs.get("min_similarity", 0.3)
        
        if not question or not kg:
            return FunctionResult(
                success=False,
                error="Missing required parameters: question and kg"
            )
        
        try:
            # Filter examples by knowledge graph (in future, could be kg-specific)
            # For now, we assume all examples are for Wikidata
            
            # Calculate similarity scores
            scored_examples = []
            for example in self._examples:
                similarity = self._calculate_similarity(question, example['question'])
                
                if similarity >= min_similarity:
                    scored_examples.append({
                        **example,
                        'similarity': similarity,
                        'kg': kg
                    })
            
            # Sort by similarity (highest first)
            scored_examples.sort(key=lambda x: x['similarity'], reverse=True)
            
            # Take top N
            top_examples = scored_examples[:limit]
            
            # Extract patterns from examples
            patterns = {}
            for example in top_examples:
                for pattern in example.get('patterns', []):
                    if pattern not in patterns:
                        patterns[pattern] = {
                            'count': 0,
                            'examples': []
                        }
                    patterns[pattern]['count'] += 1
                    patterns[pattern]['examples'].append(example['description'])
            
            return FunctionResult(
                success=True,
                result={
                    'question': question,
                    'kg': kg,
                    'examples': top_examples,
                    'patterns': patterns,
                    'total_found': len(top_examples),
                    'min_similarity_used': min_similarity
                }
            )
                    
        except Exception as e:
            return FunctionResult(
                success=False,
                error=f"Get similar examples failed: {str(e)}"
            )


class GetPropertyPatternsFunction(BaseFunction):
    """Get common usage patterns for a property."""
    
    def __init__(self):
        super().__init__(
            name="get_property_patterns",
            description="Get common SPARQL query patterns for using a property"
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
                    name="property",
                    type="string",
                    description="Property IRI",
                    required=True
                ),
                FunctionParameter(
                    name="limit",
                    type="integer",
                    description="Maximum number of patterns to return (default: 5)",
                    required=False
                )
            ]
        )
    
    async def execute(self, **kwargs) -> FunctionResult:
        kg = kwargs.get("kg")
        property_uri = kwargs.get("property")
        limit = kwargs.get("limit", 5)
        
        if not kg or not property_uri:
            return FunctionResult(
                success=False,
                error="Missing required parameters: kg and property"
            )
        
        try:
            # In a real implementation, this would analyze the knowledge graph
            # or query a pattern database. For now, we return generic patterns.
            
            # Common SPARQL patterns for properties
            common_patterns = [
                {
                    'pattern': 'SELECT ?value WHERE { ?entity <PROPERTY> ?value . }',
                    'description': 'Get values of property for any entity',
                    'variables': ['?entity', '?value'],
                    'example': f'SELECT ?value WHERE {{ ?entity <{property_uri}> ?value . }} LIMIT 5'
                },
                {
                    'pattern': 'SELECT ?entity WHERE { ?entity <PROPERTY> "literal value" . }',
                    'description': 'Find entities with specific property value',
                    'variables': ['?entity'],
                    'example': f'SELECT ?entity WHERE {{ ?entity <{property_uri}> "example value" . }} LIMIT 5'
                },
                {
                    'pattern': 'SELECT ?entity1 ?entity2 WHERE { ?entity1 <PROPERTY> ?entity2 . }',
                    'description': 'Find pairs of entities connected by property',
                    'variables': ['?entity1', '?entity2'],
                    'example': f'SELECT ?entity1 ?entity2 WHERE {{ ?entity1 <{property_uri}> ?entity2 . }} LIMIT 5'
                },
                {
                    'pattern': 'SELECT ?entity ?value WHERE { ?entity <PROPERTY> ?value . FILTER(isLiteral(?value)) }',
                    'description': 'Get literal values of property',
                    'variables': ['?entity', '?value'],
                    'example': f'SELECT ?entity ?value WHERE {{ ?entity <{property_uri}> ?value . FILTER(isLiteral(?value)) }} LIMIT 5'
                },
                {
                    'pattern': 'SELECT ?entity ?value WHERE { ?entity <PROPERTY> ?value . FILTER(isIRI(?value)) }',
                    'description': 'Get entity values of property',
                    'variables': ['?entity', '?value'],
                    'example': f'SELECT ?entity ?value WHERE {{ ?entity <{property_uri}> ?value . FILTER(isIRI(?value)) }} LIMIT 5'
                }
            ]
            
            # Limit the number of patterns
            patterns = common_patterns[:limit]
            
            # Add property-specific advice based on common property types
            advice = []
            
            # Check if property looks like a label property
            if any(label_term in property_uri.lower() for label_term in ['label', 'name', 'title']):
                advice.append("This appears to be a label property. Use it with FILTER(LANG(?label) = 'en') for English labels.")
            
            # Check if property looks like a description property
            if any(desc_term in property_uri.lower() for desc_term in ['description', 'comment', 'abstract']):
                advice.append("This appears to be a description property. Useful for providing context about entities.")
            
            # Check if property looks like a relationship property
            if any(rel_term in property_uri.lower() for rel_term in ['part', 'member', 'child', 'parent', 'subclass']):
                advice.append("This appears to be a relationship property. Useful for finding related entities.")
            
            return FunctionResult(
                success=True,
                result={
                    'property': property_uri,
                    'kg': kg,
                    'patterns': patterns,
                    'advice': advice,
                    'total_patterns': len(patterns)
                }
            )
                    
        except Exception as e:
            return FunctionResult(
                success=False,
                error=f"Get property patterns failed: {str(e)}"
            )
