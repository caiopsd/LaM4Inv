import io
import os
import time
import logging
import math

from smt.solver import InvalidFormulaError as SMTInvalidFormulaError
from code_handler.formula_handler import InvalidFormulaError as CInvalidFormulaError
from inv_smt_solver.inv_smt_solver import InvSMTSolver, CounterExample
from generator.generator import Generator
from code_handler.formula_handler import FormulaHandler
from predicate_filtering.predicate_filtering import PredicateFiltering
from llm.llm import LLM, ChatOptions

class Runner:
    def __init__(
        self, 
        inv_smt_solver: InvSMTSolver, 
        predicate_filtering: PredicateFiltering,
        generator: Generator,
        pipeline: list[tuple[LLM, float]],
        formula_handler: FormulaHandler,
        result_file_path: str,
        presence_penalty_scale: float
    ):
        self.inv_smt_solver = inv_smt_solver
        self.predicate_filtering = predicate_filtering
        self.generator = generator
        self.pipeline = pipeline
        self.formula_handler = formula_handler

        self.presence_penalty_scale = presence_penalty_scale
        
        self._result_file = self._get_result_file(result_file_path)
        self._logger = logging.getLogger(__name__)

        self.reset()

    def _get_result_file(self, result_file_path: str) -> io.TextIOWrapper:
        os.makedirs(os.path.dirname(result_file_path), exist_ok=True)
        return open(result_file_path, "w")

    def _smt_verify(self, formula: str) -> CounterExample:
        smt_lib2_candidate = self.formula_handler.to_smt_lib2(formula)
        counter_example = self.inv_smt_solver.get_counter_example(smt_lib2_candidate)
        if counter_example is not None:
            return counter_example

    def _predicate_filtering(self, formula: str) -> str:
        filtered_predicates = self.predicate_filtering.filter(formula)
        for predicate in filtered_predicates:
            if self._smt_verify(predicate) is None:
                return predicate
    
    def _verify(self, candidates: list[str]) -> tuple[str, list[str]]:
        fails = []
        for candidate in candidates:
            self._log(f'Verifying candidate: {candidate}')

            if candidate in self._fail_history:
                self._fail_history_hit += 1
                fails.append((candidate, (self._fail_history[candidate])))
                self._log(f'Candidate already in fail history: {candidate}')
                continue

            self._verified_candidates += 1

            formula = self.formula_handler.extract_formula(candidate)
            try:
                counter_example = self._smt_verify(formula)
                if counter_example is None:
                    return candidate, None
                
                fails.append((candidate, counter_example))

                self._log(f'Found counter example ({counter_example}), trying predicate filtering')
                solution = self._predicate_filtering(formula)
                if solution is not None:
                    self._log(f'Predicate filtering found solution: {solution}')
                    return solution, None
                
                self._log(f'Candidate failed verification')
            except CInvalidFormulaError as e:
                self._log(f'Invalid candidate syntax: {candidate}')
                continue
            except SMTInvalidFormulaError as e:
                self._log(f'Invalid SMT formula for candidate: {candidate}')
                continue
            except TimeoutError as e:
                self._log(f'Timeout while verifying candidate: {candidate}')
                continue
            
            self._log(f'Adding candidate to fail history: {candidate}')
            self._fail_history[candidate] = counter_example
        
        return None, fails

    def _write_log(self):
        formmated_time = time.strftime("%H:%M:%S %d/%m/%Y", time.gmtime(time.time()))
        for log in self._logs:
            print(log)
            self._result_file.write(f'{formmated_time} {log}\n')

    def _log_solution(self, solution: str, time_spent: float):
        self._log('# Result')
        if solution is not None:
            self._log(f'Solution: {solution}')
        else:
            self._log(f'No solution found')
        self._log(f'Verified candidates: {self._verified_candidates}')
        self._log(f'Run time: {time_spent}')

    def _log(self, message: str):
        self._logger.info(message)
        self._logs.append(message)

    def _close(self):
        self._result_file.close()

    def _handle_solution(self, solution: str, end_time: float):
        self._log_solution(solution, end_time)
        self._write_log()
        self.reset()
        self._close()
        return solution, end_time, self._verified_candidates
    
    def _next_pipeline_step(self) -> tuple[LLM, float]:
        if self._curr_pipeline_step_index is None:
            self._curr_pipeline_step_time = time.time()
            self._curr_pipeline_step_index = 0
            return self.pipeline[0]

        time_spent = time.time() - self._curr_pipeline_step_time
        curr_step = self.pipeline[self._curr_pipeline_step_index]
        if time_spent >= curr_step[1] and self._curr_pipeline_step_index == len(self.pipeline) - 1:
            return (None, None)
        if time_spent >= curr_step[1]:
            self._fail_history = {}
            self._fail_history_hit = 0
            self.last_fails = []
            self.generator.reset()

            self._curr_pipeline_step_index += 1
            self._curr_pipeline_step_time = time.time()
        
        return self.pipeline[self._curr_pipeline_step_index]
    
    def _get_presence_penalty(self) -> float:
        return math.tanh(self._fail_history_hit * self.presence_penalty_scale)
    
    def run(self, benchmark_id: str) -> tuple[str, float, int]:
        start_time = time.time()

        self._log(f'# Run Benchmark {benchmark_id}')

        llm, _ = self._next_pipeline_step()
        chat_options = ChatOptions()

        candidates = self.generator.generate(llm=llm)
        solution, self.last_fails = self._verify(candidates)
        if solution is not None:
            return self._handle_solution(solution, (time.time() - start_time))
        
        while True:
            llm, _ = self._next_pipeline_step()
            if llm is None:
                self._handle_solution(None, (time.time() - start_time))
                raise TimeoutError('Pipeline time exceeded')

            chat_options.presence_penalty = self._get_presence_penalty()
            
            self._log(f'Generating loop invariants candidates with model {llm} with presence penalty {chat_options.presence_penalty}')

            candidates = self.generator.generate(feedback=self.last_fails, llm=llm, chat_options=chat_options)

            self._log(f'Generated {len(candidates)} candidates')

            solution, self.last_fails = self._verify(candidates)
            if solution is not None:
                return self._handle_solution(solution, (time.time() - start_time))
            
    def reset(self):
        self._fail_history = {}
        self._fail_history_hit = 0
        self._verified_candidates = 0
        self._last_fails = []
        self._logs = []
        self._curr_pipeline_step_index = None
        self._curr_pipeline_step_time = None
        self.generator.reset()