import re

from code_handler.formula_handler import FormulaHandler, FormulaForm, InvalidCodeFormulaError

class CFormulaHandler(FormulaHandler):
    def __init__(self):
        self.operators = [
            ('||', 'or', 1),
            ('&&', 'and', 2),
            ('==', '=', 3),
            ('!=', 'distinct', 3),
            ('>=', '>=', 4),
            ('<=', '<=', 4),
            ('>', '>', 4),
            ('<', '<', 4),
            ('+', '+', 5),
            ('-', '-', 5),
            ('*', '*', 6),
            ('/', '/', 6),
            ('%', 'mod', 6)
        ]

    def extract_formula(self, expression: str) -> str:
        match = re.search(r'assert\s*\((.*)\)', expression)
        if not match:
            raise InvalidCodeFormulaError(f'C assertion "{expression}" does not match the expected format')
        
        formula = match.group(1).strip()
        return formula
    
    def negate_formula(self, formula: str) -> str:
        return f"!({formula})"

    def join_formulas(self, formulas: list[str], form: FormulaForm) -> str:
        if form == FormulaForm.DNF:
            return ' || '.join(f'({formula})' for formula in formulas)
        if form == FormulaForm.CNF:
            return ' && '.join(f'({formula})' for formula in formulas)
        
    def _is_balanced_parentheses(self, expr: str) -> bool:
        balance = 0
        for char in expr:
            if char == '(':
                balance += 1
            elif char == ')':
                balance -= 1
                if balance < 0:
                    return False
        return balance == 0
        
    def to_smt_lib2(self, formula: str) -> str:
        smt_formula = self._to_smt_lib2_formula(formula.strip())
        return smt_formula
    
    def _to_smt_lib2_formula(self, formula: str) -> str:
        formula = formula.strip()

        if formula.startswith('!'):
            inner = self._to_smt_lib2_formula(formula[1:].strip())
            return f"(not {inner})"

        if formula.startswith('(') and formula.endswith(')'):
            if self._is_balanced_parentheses(formula[1:-1]):  
                return self._to_smt_lib2_formula(formula[1:-1])

        min_precedence = float('inf')
        main_operator = None
        main_op_index = -1
        paren_level = 0

        for i in range(len(formula)):
            if formula[i] == '(':
                paren_level += 1
            elif formula[i] == ')':
                paren_level -= 1

            for c_op, smt_op, precedence in self.operators:
                if paren_level == 0 and formula[i:i+len(c_op)] == c_op:
                    if precedence < min_precedence:
                        min_precedence = precedence
                        main_operator = (c_op, smt_op)
                        main_op_index = i
        
        if main_operator:
            c_op, smt_op = main_operator
            left = formula[:main_op_index].strip()
            right = formula[main_op_index + len(c_op):].strip()

            left_smt = self._to_smt_lib2_formula(left)
            right_smt = self._to_smt_lib2_formula(right)

            return f"({smt_op} {left_smt} {right_smt})"

        return formula
    
    def get_form(self, formula: str) -> FormulaForm:
        smtlib2_formula = self.to_smt_lib2(formula)

        and_index = smtlib2_formula.find('and')
        or_index = smtlib2_formula.find('or')
        if and_index == -1 and or_index == -1:
            return None
        if and_index == -1:
            return FormulaForm.DNF
        if or_index == -1:
            return FormulaForm.CNF
        if and_index < or_index:
            return FormulaForm.CNF
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