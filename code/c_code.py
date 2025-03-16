import re

from code.code import Code

class CCode(Code):
    def __init__(self, c_file_path: str):
        with open(c_file_path, 'r') as f:
            self.code = f.read()

    def _get_precondition_code(self) -> str:
        return self.code.split('while')[0] if 'while' in self.code else self.code

    def _extract_variables_definitions_assertions(self) -> list[str]:
        pattern = re.compile(r'\bint\s+([^;]+);')
        matches = re.findall(pattern, self._get_precondition_code())
        assertions = []
        for match in matches:
            declarations = match.split(',')
            for declaration in declarations:
                if '=' in declaration:
                    var_name, value = [x.strip() for x in declaration.split('=')]
                    assertions.append(f'assert({var_name} == {value});')

        return assertions

    def _extract_assignments_assertions(self) -> list[str]:
        pattern = re.compile(r'\b(\w+\s*=\s*\d+);')
        matches = re.findall(pattern, self._get_precondition_code())
        assertions = []
        for match in matches:
            var_name, value = [x.strip() for x in match.split('=')]
            assertions.append(f'assert({var_name} == {value});')
        
        return assertions
    
    def _extract_assume_assertions(self) -> list[str]:
        pattern = re.compile(r'assume\(([^)]+)\);')
        matches = re.findall(pattern, self._get_precondition_code())
        assertions = []
        for match in matches:
            assertions.append(f'assert({match});')
        
        return assertions


    def extract_loop_preconditions(self) -> list[str]:
        variable_definitions_assertions = self._extract_variables_definitions_assertions()
        assignments_assertions = self._extract_assignments_assertions()
        assume_assertions = self._extract_assume_assertions()

        return variable_definitions_assertions + assignments_assertions + assume_assertions

    def get_code(self) -> str:
        return self.code