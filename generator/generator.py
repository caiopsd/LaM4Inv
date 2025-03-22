from enum import Enum
import re

from llm.llm import LLM, ChatOptions, Chat
from inv_smt_solver.counter_example import CounterExample, CounterExampleKind
from code_handler.code_handler import CodeHandler

class Generator:
    def __init__(self, code_handler: CodeHandler):
        self.code_handler = code_handler
        self._chat = Chat()

    def _get_base_llm_prompt(self) -> str:
        return f"""{self.code_handler.get_code()}
Print loop invariants as valid {self.code_handler.get_language().value} assertions that help prove the assertion.

A correct loop invariant holds for all the following properties:
    - Reachability: means that the loop invariant I can be derived based on the pre-condition P, i.e. P ⇒ I. For this property, in order to get a correct answer, you may want to consider the initial situation where the program won't enter the loop.
    - Provability: means that after unsatisfying loop condition B, we can prove the post-condition Q, i.e. (I ∧ ¬ B) ⇒ Q. For this property, in order to get a correct answer, you may want to consider the special case of the program executing to the end of the loop. If some of the preconditions are also loop invariant, you need to add them to your answer as well.
    - Inductiveness: means that if the program state satisfies loop condition B, the new state obtained after the loop execution S still satisfies, i.e. {{I ∧ B}} S {{I}}.For this property, in order to get a correct answer, You may want to consider the special case of the program executing to the end of the loop.

In order to get a correct answer, You may want to consider both the situation of not entering the loop and the situation of jumping out of the loop.

If some of the preconditions are also loop invariant, you need to add them to your answer as well.

Don't explain. Your answer should contain only '{self.code_handler.get_assert_format()}' lines.
"""
    
    def _format_fail_history(self, fail_history: dict[str, CounterExample]) -> str:
        history = ""
        for candidate, counter_example in fail_history.items():
            if counter_example.kind == CounterExampleKind.POSITIVE:
                history += f'   - "{candidate}" is too strict and breaks reachability. With counter example given by the SMT solver: {counter_example}\n'
            elif counter_example.kind == CounterExampleKind.NEGATIVE:
                history += f'   - "{candidate}" is too weak and breaks provability. With counter example given by the SMT solver: {counter_example}\n'
            elif counter_example.kind == CounterExampleKind.INTERMEDIATE:
                history += f'   - "{candidate}" break inductiveness. With counter example given by the SMT solver: {counter_example}\n'
        return history
    
    def _get_feedback_llm_prompt(self, fail_history: dict[str, CounterExample]) -> str:
        return f"""Previous answers were verified and are not correct as they break some properties of a correct loop invariant.

 Please generate new loop invariants.

**IMPORTANT:** Only genereate loop invariant that are **NOT INCLUDED IN THE FOLLOWING FAILURE HISTORY OR IN ANY OF YOUR PREVIOUS RESPONSES.**

# Failure History
{self._format_fail_history(fail_history)}
"""
        
    def _parse_llm_output(self, output: str) -> list[str]:
        expressions = []
        pattern = re.compile(self.code_handler.get_assert_pattern())
        matches = pattern.findall(output)
        for match in matches:
            expressions.append(match)
        return expressions

    def generate(self, llm: LLM, fail_history: dict[str, CounterExample] = None, chat_options: ChatOptions = None) -> list[str]:
        if fail_history:
            prompt = self._get_feedback_llm_prompt(fail_history)
        else:
            prompt = self._get_base_llm_prompt()
        self._chat.add_user_message(prompt)

        output = llm.chat(self._chat, chat_options)
        self._chat.add_assistant_response(output)

        return self._parse_llm_output(output)

    def reset(self):
        self._chat.reset()