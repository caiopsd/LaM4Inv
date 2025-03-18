import re

from conde_handler.code_handler import CodeHandler
from conde_handler.language import Language

class CCodeHandler(CodeHandler):
    def __init__(self, code: str):
        self.code = code
        self.language = Language.C

    def assert_to_smt_lib2(self, assertion: str) -> str:
        assert_match = re.search(r'assert\s*\((.*)\)', assertion)
        if not assert_match:
            return assertion
        
        condition = assert_match.group(1).strip()
        
        smt_condition = self._convert_condition(condition)
        
        return f"(assert {smt_condition})"
    
    def _convert_condition(self, condition: str) -> str:
        operators = [
            ('||', 'or'),
            ('&&', 'and'),
            ('==', '='),
            ('!=', 'distinct'),
            ('>=', '>='),
            ('<=', '<='),
            ('>', '>'),
            ('<', '<'),
        ]
        
        if condition.startswith('!') and len(condition) > 1:
            return f"(not {self._convert_condition(condition[1:])})"
        
        for c_op, smt_op in operators:
            paren_level = 0
            # Search for the operator
            for i in range(len(condition) - len(c_op) + 1):
                if condition[i] == '(':
                    paren_level += 1
                elif condition[i] == ')':
                    paren_level -= 1
                
                # If we found the operator outside of parentheses
                if paren_level == 0 and condition[i:i+len(c_op)] == c_op:
                    # Recursively convert both sides
                    left = condition[:i].strip()
                    right = condition[i+len(c_op):].strip()
                    
                    left_smt = self._convert_condition(left)
                    right_smt = self._convert_condition(right)
                    
                    return f"({smt_op} {left_smt} {right_smt})"
        
        # Handle parenthesized expressions
        if condition.startswith('(') and condition.endswith(')'):
            paren_level = 0
            for i in range(1, len(condition) - 1):
                if condition[i] == '(':
                    paren_level += 1
                elif condition[i] == ')':
                    paren_level -= 1
                
                if paren_level < 0:
                    break
            
            if paren_level == 0:
                return self._convert_condition(condition[1:-1])
        
        return condition

    def get_code(self) -> str:
        return self.code

    def get_language(self) -> Language:
        return self.language
    
    def get_assert_format(self) -> str:
        return 'assert(...);'
    
    def get_assert_pattern(self) -> str:
        return r'(assert\s*\(.*\));'
