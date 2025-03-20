import re

from code_handler.code_handler import CodeHandler, Language

class CCodeHandler(CodeHandler):
    def __init__(self, code: str):
        self.code = code
        self.language = Language.C

    def get_code(self) -> str:
        return self.code

    def get_language(self) -> Language:
        return self.language
    
    def get_assert_format(self) -> str:
        return 'assert(...);'

    def get_assert_pattern(self) -> str:
        return r'assert\(.*\);'
    
    def add_invariant_assertions(self, formula: str):
        pattern = r'([ \t]*)(while\s*\(.*?\)\s*\{)((?:[^{}]*|\{[^{}]*\})*\})'
        assertion = f'assert({formula});'
        code = re.sub(pattern, rf'\1{assertion}\n\1\2\n\1\1{assertion}\3\n\1{assertion}', self.code)

        if '#include <assert.h>' not in code:
            code = '#include <assert.h>\n' + code

        return code