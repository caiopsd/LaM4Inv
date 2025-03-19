import re

from formula_handler.formula_handler import FormulaHandler, FormulaForm

class CFormulaHandler(FormulaHandler):
    def extract_formula(self, expression: str) -> str:
        match = re.search(r'assert\s*\((.*)\)', expression)
        if not match:
            raise ValueError(f'C assertion "{expression}" does not match the expected format')
        
        formula = match.group(1).strip()
        return formula
    
    def negate_formula(self, formula: str) -> str:
        return f"!({formula})"

    def join_formulas(self, formulas: list[str], form: FormulaForm) -> str:
        if form == FormulaForm.DNF:
            return ' || '.join(f'({formula})' for formula in formulas)
        if form == FormulaForm.CNF:
            return ' && '.join(f'({formula})' for formula in formulas)
        
    def to_smt_lib2_assert(self, formula: str) -> str:
        smt_formula = self._to_smt_lib2_formula(formula)
        
        return f"(assert {smt_formula})"
    
    def _to_smt_lib2_formula(self, formula: str) -> str:
        operators = [
            ('||', 'or'),
            ('&&', 'and'),
            ('==', '='),
            ('!=', 'distinct'),
            ('>=', '>='),
            ('<=', '<='),
            ('>', '>'),
            ('<', '<'),
            ('+', '+'),
            ('-', '-'),
            ('*', '*'),
            ('/', '/'),
            ('%', 'mod')
        ]
        
        if formula.startswith('!') and len(formula) > 1:
            return f"(not {self._to_smt_lib2_formula(formula[1:])})"
        
        for c_op, smt_op in operators:
            paren_level = 0
            # Search for the operator
            for i in range(len(formula) - len(c_op) + 1):
                if formula[i] == '(':
                    paren_level += 1
                elif formula[i] == ')':
                    paren_level -= 1
                
                # If we found the operator outside of parentheses
                if paren_level == 0 and formula[i:i+len(c_op)] == c_op:
                    # Recursively convert both sides
                    left = formula[:i].strip()
                    right = formula[i+len(c_op):].strip()
                    
                    left_smt = self._to_smt_lib2_formula(left)
                    right_smt = self._to_smt_lib2_formula(right)
                    
                    return f"({smt_op} {left_smt} {right_smt})"
        
        # Handle parenthesized expressions
        if formula.startswith('(') and formula.endswith(')'):
            paren_level = 0
            for i in range(1, len(formula) - 1):
                if formula[i] == '(':
                    paren_level += 1
                elif formula[i] == ')':
                    paren_level -= 1
                
                if paren_level < 0:
                    break
            
            if paren_level == 0:
                return self._to_smt_lib2_formula(formula[1:-1])
        
        return formula
    
    def get_form(self, formula: str) -> FormulaForm:
        smtlib2_assertion = self.to_smt_lib2_assert(formula)
        if smtlib2_assertion[9:12] == 'and':
            return FormulaForm.CNF
        if smtlib2_assertion[9:12] == 'or ':
            return FormulaForm.DNF
        
    def extract_predicates(self, formula: str) -> list[str]:
        form = self.get_form(formula)
        operator = '||'
        if form == FormulaForm.CNF:
            operator = '&&'

        predicates = []
        bracket_count = 0
        start = 0
        for i, char in enumerate(formula):
            if char == '(':
                bracket_count += 1
            elif char == ')':
                bracket_count -= 1
            elif bracket_count == 0 and formula[i:i + len(operator)] == operator:
                predicates.append(formula[start:i].strip())
                start = i + len(operator)
                
        predicates.append(formula[start:].strip())

        return predicates