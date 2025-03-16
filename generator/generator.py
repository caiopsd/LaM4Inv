from enum import Enum
import re

from llm.llm import LLM
from smt.solver import Solver as SMTSolver
from inv_smt_solver.counter_example import CounterExample, CounterExampleKind

class GeneratorPhase(Enum):
    BASE = 1
    NOT_REACHABLE = 2
    NOT_PROVABLE = 3
    NOT_INDUCTIVE = 4

class Generator:
    def __init__(self, llm: LLM, smt_solver: SMTSolver):
        self.llm = llm
        self.smt_solver = smt_solver

    def _get_base_llm_prompt(self, code: str) -> str:
        return f"""{code} Print loop invariants as valid SMT-LIB2 assertions that help prove the assertion.
        In order to get a correct answer, You may want to consider both the situation of not entering the loop and the situation of jumping out of the loop.
        If some of the preconditions are also loop invariant, you need to add them to your answer as well.
        Use 'and' or 'or' if necessary. Don't explain. Your answer should be 'assert(...)''
        """

    def _get_not_reachable_llm_prompt(self, code: str, previous_answer: str, counter_example: str) -> str:
        return f"""{code} Print loop invariants as valid SMT-LIB2 assertions that help prove the assertion.
        Your previous answer '{previous_answer}' is too strict and not reachable.
        The Reachability of the loop invariant means that the loop invariant I can be derived based on the pre-condition P, i.e. P ⇒ I.
        The following is a counterexample given by z3: {counter_example}
        In order to get a correct answer, You may want to consider the initial situation where the program won't enter the loop. 
        Use 'and' or 'or' if necessary. Don't explain. Your answer should be 'assert(...)''
        """
    
    def _get_not_provable_llm_prompt(self, code: str, previous_answer: str, counter_example: str) -> str:
        return f"""{code} Print loop invariants as valid SMT-LIB2 assertions that help prove the assertion.
        Your previous answer '{previous_answer}' is too weak and not provable.
        The Provability of the loop invariant means that after unsatisfying loop condition B, we can prove the post-condition Q, i.e. (I ∧ ¬ B) ⇒ Q.
        The following is a counterexample given by z3: {counter_example}
        In order to get a correct answer, you may want to consider the special case of the program executing to the end of the loop. If some of the preconditions are also loop invariant, you need to add them to your answer as well.
        Use 'and' or 'or' if necessary. Don't explain. Your answer should be 'assert(...)''
        """
    
    def _get_not_inductive_llm_prompt(self, code: str, previous_answer: str, counter_example: str) -> str:
        return f"""{code} Print loop invariants as valid SMT-LIB2 assertions that help prove the assertion.
        Your previous answer '{previous_answer}' is not inductive.
        The Inductive of the loop invariant means that if the program state satisfies loop condition B, the new state obtained after the loop execution S still satisfies, i.e. {{I ∧ B}} S {{I}}.
        The following is a counterexample given by z3: {counter_example}
        In order to get a correct answer, You may want to consider the special case of the program executing to the end of the loop.
        Use 'and' or 'or' if necessary. Don't explain. Your answer should be 'assert(...)'
        """
    
    def _get_llm_prompt(self, phase: GeneratorPhase, code: str, previous_answer: str = None, counter_example: str = None) -> str:
        if phase != GeneratorPhase.BASE and (previous_answer is None or counter_example is None):
            raise ValueError("previous_answer and counter_example must be provided for non-base phases.")
        
        if phase == GeneratorPhase.BASE:
            return self._get_base_llm_prompt(code)
        elif phase == GeneratorPhase.NOT_REACHABLE:
            return self._get_not_reachable_llm_prompt(code, previous_answer, counter_example)
        elif phase == GeneratorPhase.NOT_PROVABLE:
            return self._get_not_provable_llm_prompt(code, previous_answer, counter_example)
        elif phase == GeneratorPhase.NOT_INDUCTIVE:
            return self._get_not_inductive_llm_prompt(code, previous_answer, counter_example)
        
    def _parse_llm_output(self, output: str) -> list[str]:
        expressions = []
        pattern = re.compile(r"assert\(.*\)")
        matches = pattern.findall(output)
        for match in matches:
            if self.smt_solver.is_valid_expression(match):
                expressions.append(match)
        return expressions

    def generate(self, code: str, previous_answer: str = None, counter_example: CounterExample = None) -> list[str]:
        phase = GeneratorPhase.BASE
        if counter_example and counter_example.kind == CounterExampleKind.POSITIVE:
            phase = GeneratorPhase.NOT_REACHABLE
        if counter_example and counter_example.kind == CounterExampleKind.NEGATIVE:
            phase = GeneratorPhase.NOT_PROVABLE
        if counter_example and counter_example.kind == CounterExampleKind.INTERMEDIATE:
            phase = GeneratorPhase.NOT_INDUCTIVE
        
        prompt = self._get_llm_prompt(phase, code, previous_answer, counter_example.assignment)
        output = self.llm.prompt(prompt)
        return self._parse_llm_output(output)
