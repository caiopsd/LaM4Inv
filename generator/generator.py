from enum import Enum
from llm.llm import LLM

class PHASE(Enum):
    BASE = 1
    NOT_REACHABLE = 2
    NOT_PROVABLE = 3
    NOT_INDUCTIVE = 4
    SIMPLE = 5

class Generator:
    def __init__(self, llm: LLM):
        self.llm = llm

    def _get_base_prompt(self, code: str) -> str:
        return f"""{code} Print loop invariants as valid C assertions that help prove the assertion.
        In order to get a correct answer, You may want to consider both the situation of not entering the loop and the situation of jumping out of the loop.
        If some of the preconditions are also loop invariant, you need to add them to your answer as well.
        Use '&&' or '||' if necessary. Don't explain. Your answer should be 'assert(...);'
        """

    def _get_not_reachable_prompt(self, code: str, previous_answer: str, counter_example: str) -> str:
        return f"""{code} Print loop invariants as valid C assertions that help prove the assertion.
        Your previous answer '{previous_answer}' is too strict and not reachable.
        The Reachability of the loop invariant means that the loop invariant I can be derived based on the pre-condition P, i.e. P ⇒ I.
        The following is a counterexample given by z3: {counter_example}
        In order to get a correct answer, You may want to consider the initial situation where the program won't enter the loop. 
        Use '&&' or '||' if necessary. Don't explain. Your answer should be 'assert(...);'
        """
    
    def _get_not_provable_prompt(self, code: str, previous_answer: str, counter_example: str) -> str:
        return f"""{code} Print loop invariants as valid C assertions that help prove the assertion.
        Your previous answer '{previous_answer}' is too weak and not provable.
        The Provability of the loop invariant means that after unsatisfying loop condition B, we can prove the post-condition Q, i.e. (I ∧ ¬ B) ⇒ Q.
        The following is a counterexample given by z3: {counter_example}
        In order to get a correct answer, you may want to consider the special case of the program executing to the end of the loop. If some of the preconditions are also loop invariant, you need to add them to your answer as well.
        Use '&&' or '||' if necessary. Don't explain. Your answer should be 'assert(...);'
        """
    
    def _get_not_inductive_prompt(self, code: str, previous_answer: str, counter_example: str) -> str:
        return f"""{code} Print loop invariants as valid C assertions that help prove the assertion.
        Your previous answer '{previous_answer}' is not inductive.
        The Inductive of the loop invariant means that if the program state satisfies loop condition B, the new state obtained after the loop execution S still satisfies, i.e. {{I ∧ B}} S {{I}}.
        The following is a counterexample given by z3: {counter_example}
        In order to get a correct answer, You may want to consider the special case of the program executing to the end of the loop.
        Use '&&' or '||' if necessary. Don't explain. Your answer should be 'assert(...);
        """
    
    def _get_simple_prompt(self, code: str) -> str:
        return f"""{code} Print loop invariants as valid C assertions that help prove the assertion.
        Use '&&' or '||' if necessary. Don't explain. Your answer should be 'assert(...);'
        """
    
    def _get_prompt(self, phase: PHASE, code: str, previous_answer: str, counter_example: str) -> str:
        if phase == PHASE.BASE:
            return self._get_base_prompt(code)
        elif phase == PHASE.NOT_REACHABLE:
            return self._get_not_reachable_prompt(code, previous_answer, counter_example)
        elif phase == PHASE.NOT_PROVABLE:
            return self._get_not_provable_prompt(code, previous_answer, counter_example)
        elif phase == PHASE.NOT_INDUCTIVE:
            return self._get_not_inductive_prompt(code, previous_answer, counter_example)
        elif phase == PHASE.SIMPLE:
            return self._get_simple_prompt(code)

    def get_invariants(self, code: str, phase: PHASE, previous_answer: str, counter_example: str) -> list[str]:
        prompt = self._get_prompt(phase, code, previous_answer, counter_example)
        answer = self.llm.prompt(prompt)
