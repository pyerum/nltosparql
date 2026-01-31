"""SPARQL query validation utilities."""

import re
from typing import Dict, List, Optional, Tuple
from .qlever_client import SPARQLResult, QLeverClient


class QueryValidator:
    """Validator for SPARQL queries."""
    
    @staticmethod
    def validate_syntax(query: str) -> Tuple[bool, List[str]]:
        """
        Validate SPARQL query syntax.
        
        Args:
            query: SPARQL query string
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Basic syntax checks
        if not query.strip():
            errors.append("Query is empty")
            return False, errors
        
        # Check for common SPARQL keywords
        query_upper = query.upper()
        
        # Should start with SELECT, ASK, CONSTRUCT, DESCRIBE, or PREFIX
        # Remove PREFIX declarations for checking
        check_query = query_upper
        # Remove all PREFIX declarations for checking
        import re
        check_query = re.sub(r'PREFIX\s+\w+:\s*<[^>]+>', '', check_query)
        check_query = check_query.strip()
        
        if not (check_query.startswith('SELECT') or 
                check_query.startswith('ASK') or
                check_query.startswith('CONSTRUCT') or
                check_query.startswith('DESCRIBE')):
            errors.append("Query must start with SELECT, ASK, CONSTRUCT, or DESCRIBE (after PREFIX declarations)")
        
        # Check for balanced braces
        brace_count = 0
        for char in query:
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count < 0:
                    errors.append("Unbalanced braces: closing brace without opening")
                    break
        
        if brace_count > 0:
            errors.append(f"Unbalanced braces: {brace_count} unclosed brace(s)")
        
        # Check for common syntax errors
        if '??' in query:
            errors.append("Query contains '??' which is invalid syntax")
        
        # Check for proper variable declarations in SELECT
        if query_upper.startswith('SELECT'):
            # Check for SELECT * or SELECT with variables
            select_part = query[:100].upper()
            if 'SELECT *' in select_part:
                # SELECT * is valid
                pass
            elif 'SELECT' in select_part and 'WHERE' in select_part:
                # Check if there are variables between SELECT and WHERE
                select_idx = select_part.find('SELECT')
                where_idx = select_part.find('WHERE')
                between = query[select_idx + 6:where_idx].strip()
                if not between:
                    errors.append("SELECT query must specify variables or use SELECT *")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def extract_variables(query: str) -> List[str]:
        """
        Extract variables from a SPARQL query.
        
        Args:
            query: SPARQL query string
            
        Returns:
            List of variable names
        """
        variables = []
        
        # Find all variables (starting with ? or $)
        var_pattern = r'[?$](\w+)'
        matches = re.findall(var_pattern, query)
        
        # Remove duplicates while preserving order
        seen = set()
        for var in matches:
            if var not in seen:
                seen.add(var)
                variables.append(var)
        
        return variables
    
    @staticmethod
    def extract_prefixes(query: str) -> Dict[str, str]:
        """
        Extract PREFIX declarations from a SPARQL query.
        
        Args:
            query: SPARQL query string
            
        Returns:
            Dictionary mapping prefixes to URIs
        """
        prefixes = {}
        
        # Find all PREFIX declarations
        prefix_pattern = r'PREFIX\s+(\w+):\s*<([^>]+)>'
        matches = re.findall(prefix_pattern, query, re.IGNORECASE)
        
        for prefix, uri in matches:
            prefixes[prefix] = uri
        
        return prefixes
    
    @staticmethod
    async def validate_with_endpoint(
        client: QLeverClient,
        query: str,
        explain: bool = False
    ) -> Tuple[bool, Optional[str], Optional[SPARQLResult]]:
        """
        Validate query by executing it with EXPLAIN or checking syntax.
        
        Args:
            client: QLever client
            query: SPARQL query to validate
            explain: Whether to use EXPLAIN instead of executing
            
        Returns:
            Tuple of (is_valid, error_message, explain_result)
        """
        # First, check syntax
        is_valid, errors = QueryValidator.validate_syntax(query)
        if not is_valid:
            return False, f"Syntax errors: {', '.join(errors)}", None
        
        # Try to execute with EXPLAIN if requested
        if explain:
            explain_query = f"EXPLAIN {query}"
            result = await client.execute_query(explain_query, limit=1)
            
            if result.success:
                return True, None, result
            else:
                return False, f"EXPLAIN failed: {result.error}", None
        
        # Otherwise, just check if it can be parsed by executing with LIMIT 0
        # Many endpoints support LIMIT 0 for validation
        if 'LIMIT' not in query.upper():
            test_query = f"{query} LIMIT 0"
        else:
            test_query = query
        
        result = await client.execute_query(test_query, limit=0)
        
        if result.success:
            return True, None, result
        else:
            # Check if error is just due to LIMIT 0 not being supported
            # Try a different validation approach
            return False, f"Query validation failed: {result.error}", None
    
    @staticmethod
    def format_query(query: str) -> str:
        """
        Format SPARQL query for better readability.
        
        Args:
            query: SPARQL query string
            
        Returns:
            Formatted query
        """
        # Basic formatting: ensure newlines after keywords
        formatted = query
        
        # Add newlines after certain keywords
        keywords = ['SELECT', 'WHERE', 'OPTIONAL', 'FILTER', 'ORDER BY', 'LIMIT', 'OFFSET']
        
        for keyword in keywords:
            pattern = rf'({keyword}\b)'
            replacement = rf'\1\n'
            formatted = re.sub(pattern, replacement, formatted, flags=re.IGNORECASE)
        
        # Indent WHERE clause content
        lines = formatted.split('\n')
        formatted_lines = []
        in_where = False
        indent_level = 0
        
        for line in lines:
            stripped = line.strip()
            
            if 'WHERE' in stripped.upper():
                in_where = True
                formatted_lines.append(line)
                continue
            
            if in_where:
                if stripped.startswith('}'):
                    in_where = False
                    formatted_lines.append(line)
                else:
                    # Indent based on braces
                    if '{' in line:
                        formatted_lines.append('  ' * indent_level + line.lstrip())
                        indent_level += 1
                    elif '}' in line:
                        indent_level = max(0, indent_level - 1)
                        formatted_lines.append('  ' * indent_level + line.lstrip())
                    else:
                        formatted_lines.append('  ' * indent_level + line.lstrip())
            else:
                formatted_lines.append(line)
        
        return '\n'.join(formatted_lines)
