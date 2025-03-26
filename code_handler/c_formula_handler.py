import re

from pycparser import c_parser, c_ast

from code_handler.formula_handler import FormulaHandler, FormulaForm, InvalidCodeFormulaError

class SMTTranslatorVisitor(c_ast.NodeVisitor):
    def __init__(self):
        super().__init__()

    def visit_BinaryOp(self, node):
        left = self.visit(node.left)
        right = self.visit(node.right)
        op = self.map_operator(node.op)
        return f"({op} {left} {right})"

    def visit_UnaryOp(self, node):
        operand = self.visit(node.expr)
        if node.op == '!':
            return f"(not {operand})"
        if node.op == '-':
            return f"(- {operand})"
        raise InvalidCodeFormulaError(f"Unsupported unary operator: {node.op}")

    def visit_ID(self, node):
        return node.name

    def visit_Constant(self, node):
        value = node.value
        return re.sub(r'(?i)(u|l|f)+$', '', value)

    def visit_FuncCall(self, node):
        name = node.name.name if isinstance(node.name, c_ast.ID) else None
        if name == 'pow':
            args = node.args.exprs
            if len(args) != 2:
                raise InvalidCodeFormulaError("pow() expects exactly 2 arguments")
            left = self.visit(args[0])
            right = self.visit(args[1])
            return f"(^ {left} {right})"
        else:
            raise InvalidCodeFormulaError(f"Unsupported function: {name}")

    def map_operator(self, op):
        return {
            '&&': 'and',
            '||': 'or',
            '==': '=',
            '!=': 'distinct',
            '>=': '>=',
            '<=': '<=',
            '>': '>',
            '<': '<',
            '+': '+',
            '-': '-',
            '*': '*',
            '/': '/',
            '%': 'mod'
        }.get(op, None) or InvalidCodeFormulaError(f"Unsupported binary operator: {op}")

class CSMTLIB2Translator:
    def __init__(self):
        self.parser = c_parser.CParser()

    def translate_expression(self, expression: str) -> str:
        expression = self._rewrite_ternary(expression)
        try:
            ast = self.parser.parse(f"void f() {{ int __res = {expression}; }}")
            decl = ast.ext[0].body.block_items[0].init
            visitor = SMTTranslatorVisitor()
            return visitor.visit(decl)
        except Exception as e:
            raise InvalidCodeFormulaError(str(e))
        
    def _rewrite_ternary(self, expr: str) -> str:
        pattern = r'([^?]+)\s*\?\s*([^:]+)\s*:\s*([^)]+)'
        repl = r'((\1) && (\2)) || (!(\1) && (\3))' # https://en.wikipedia.org/wiki/Conditioned_disjunction
        return re.sub(pattern, repl, expr)

class CFormulaHandler(FormulaHandler):
    def __init__(self):
        self.smtlib2_translator = CSMTLIB2Translator()

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
        return self.smtlib2_translator.translate_expression(formula)

    def extract_formula(self, expression: str) -> str:
        match = re.search(r'assert\s*\((.*)\)', expression)
        if not match:
            raise InvalidCodeFormulaError(f'C assertion "{expression}" does not match the expected format')
        return match.group(1).strip()

    def negate_formula(self, formula: str) -> str:
        return f"!({formula})"

    def join_formulas(self, formulas: list[str], form: FormulaForm) -> str:
        if form == FormulaForm.DNF:
            return ' || '.join(f'({formula})' for formula in formulas)
        if form == FormulaForm.CNF:
            return ' && '.join(f'({formula})' for formula in formulas)

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
        return FormulaForm.CNF if and_index < or_index else FormulaForm.DNF

    def extract_predicates(self, formula: str) -> list[str]:
        form = self.get_form(formula)
        operator = '||' if form == FormulaForm.DNF else '&&'
        predicates = []
        bracket_count = 0
        start = 0
        for i in range(len(formula)):
            if formula[i] == '(':
                bracket_count += 1
            elif formula[i] == ')':
                bracket_count -= 1
            elif bracket_count == 0 and formula[i:i + len(operator)] == operator:
                predicates.append(formula[start:i].strip())
                start = i + len(operator)
        predicates.append(formula[start:].strip())
        return predicates
