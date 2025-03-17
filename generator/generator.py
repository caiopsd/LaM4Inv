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
        return f"""{code}
Print loop invariants as valid SMT-LIB2 assertions that help prove the assertion.
In order to get a correct answer, You may want to consider both the situation of not entering the loop and the situation of jumping out of the loop.
If some of the preconditions are also loop invariant, you need to add them to your answer as well.
Don't explain. Your answer should contain only  '(assert(...))' lines.
"""
    
    def _format_fail_history(self, fail_history: dict[str, CounterExample]) -> str:
        history = ""
        for candidate, counter_example in fail_history.items():
            if counter_example.kind == CounterExampleKind.POSITIVE:
                history += f"'{candidate}' is too strict and breaks reachability. With counter example given by z3: {counter_example}\n"
            elif counter_example.kind == CounterExampleKind.NEGATIVE:
                history += f"'{candidate}' is too weak and breaks provability. With counter example given by z3: {counter_example}\n"
            elif counter_example.kind == CounterExampleKind.INTERMEDIATE:
                history += f"'{candidate}' is breaks inductive. With counter example given by z3: {counter_example}\n"
        return history
    
    def _get_feedback_llm_prompt(self, code: str, fail_history: dict[str, CounterExample]) -> str:
        return f"""{code}
Print loop invariants as valid SMT-LIB2 assertions that help prove the assertion.
Discard the following loop invariants as they are not correct:
{self._format_fail_history(fail_history)}

The Reachability of the loop invariant means that the loop invariant I can be derived based on the pre-condition P, i.e. P ⇒ I. For this property, in order to get a correct answer, you may want to consider the initial situation where the program won't enter the loop.
The Provability of the loop invariant means that after unsatisfying loop condition B, we can prove the post-condition Q, i.e. (I ∧ ¬ B) ⇒ Q. For this property, in order to get a correct answer, you may want to consider the special case of the program executing to the end of the loop. If some of the preconditions are also loop invariant, you need to add them to your answer as well.
The Inductive of the loop invariant means that if the program state satisfies loop condition B, the new state obtained after the loop execution S still satisfies, i.e. {{I ∧ B}} S {{I}}.For this property, in order to get a correct answer, You may want to consider the special case of the program executing to the end of the loop.

Don't explain. Your answer should contain only '(assert(...))' lines.
"""
        
    def _parse_llm_output(self, output: str) -> list[str]:
        expressions = []
        pattern = re.compile(r"\(assert\s*\(.*\)\)")
        matches = pattern.findall(output)
        for match in matches:
            expressions.append(match)
        return expressions

    def generate(self, code: str, fail_history: dict[str, CounterExample] = None) -> list[str]:
        prompt = self._get_base_llm_prompt(code)
        if fail_history is not None:
            prompt = self._get_feedback_llm_prompt(code, fail_history)
        
        output = self.llm.prompt(prompt)
        return self._parse_llm_output(output)
