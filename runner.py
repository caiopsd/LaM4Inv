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
        inference_timeout: int,
        max_verified_candidates: int,
        presence_penalty_scale: float
    ):
        self.inv_smt_solver = inv_smt_solver
        self.predicate_filtering = predicate_filtering
        self.generator = generator
        self.pipeline = pipeline
        self.formula_handler = formula_handler

        self.inference_timeout = inference_timeout
        self.max_verified_candidates = max_verified_candidates
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

    def _bmc_verify(self, formula: str) -> str:
        filtered_predicates = self.predicate_filtering.filter(formula)
        for predicate in filtered_predicates:
            if self._smt_verify(predicate) is None:
                return predicate

    def _generate_candidates_from_feedback(self, llm: LLM) -> list[str]:
        new_candidates = self.generator.generate(fail_history=self._fail_history, llm=llm)
        return new_candidates
    
    def _verify(self, candidates) -> str:
        for candidate in candidates:
            self._log(f'Verifying candidate: {candidate}')

            if candidate in self._fail_history:
                self._fail_history_hit += 1
                self._log(f'Candidate already in fail history: {candidate}')
                continue

            self._verified_candidates += 1

            formula = self.formula_handler.extract_formula(candidate)
            try:
                counter_example = self._smt_verify(formula)
                if counter_example is None:
                    return candidate
                
                solution = self._bmc_verify(formula)
                if solution is not None:
                    return solution
                
                self._log(f'Found counter example: {counter_example}')
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
            self._log(f'Solution: no solution found')
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
        self._close()
        return solution, end_time, self._verified_candidates
    
    def _next_pipeline_step(self, consumed: float) -> tuple[LLM, float]:
        next_step = max((step for step in self.pipeline if step[1] <= consumed), key=lambda x: x[1])
        if next_step != self._curr_pipeline_step:
            self._fail_history = {}
            self._fail_history_hit = 0
            self.generator.reset()
            self._curr_pipeline_step = next_step
        return next_step
    
    def run(self, benchmark_id: str) -> tuple[str, float, int]:
        start_time = time.time()

        self._log(f'# Run Benchmark {benchmark_id}')

        llm, _ = self._next_pipeline_step(0)
        chat_options = ChatOptions()

        candidates = self.generator.generate(llm=llm, chat_options=chat_options)
        solution = self._verify(candidates)
        if solution is not None:
            return self._handle_solution(solution, (time.time() - start_time))
        
        while self._verified_candidates < self.max_verified_candidates:
            time_spent = time.time() - start_time
            if time_spent >= self.inference_timeout:
                self._handle_solution(None, time_spent)
                raise TimeoutError("Inference timeout")
            
            consumed_time_budget = time_spent / self.inference_timeout
            consumed_verification_budget = self._verified_candidates / self.max_verified_candidates
            llm, _ = self._next_pipeline_step(max(consumed_time_budget, consumed_verification_budget))

            chat_options.presence_penalty = math.tanh(self._fail_history_hit * self.presence_penalty_scale)
            self._log(f'Presence penalty: {chat_options.presence_penalty}')
            
            self._log(f'Generating loop invariants candidates with model {llm}')

            candidates = self._generate_candidates_from_feedback(llm)

            self._log(f'Generated {len(candidates)} candidates')

            solution = self._verify(candidates)
            if solution is not None:
                return self._handle_solution(solution, (time.time() - start_time))
            
        self.reset()
        
        return self._handle_solution(None, (time.time() - start_time))

    def reset(self):
        self._fail_history = {}
        self._fail_history_hit = 0
        self._verified_candidates = 0
        self._logs = []
        self._curr_pipeline_step = None
        self.generator.reset()