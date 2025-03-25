import io
import os
import time
import logging
import math

from bmc.bmc import InvalidCodeError
from smt.solver import InvalidSMTLIB2FormulaError
from code_handler.formula_handler import InvalidCodeFormulaError
from inv_smt_solver.inv_smt_solver import InvSMTSolver
from generator.generator import Generator
from code_handler.formula_handler import FormulaHandler
from code_handler.code_handler import CodeHandler
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
        code_handler: CodeHandler,
        result_file_path: str,
        presence_penalty_scale: float,
        max_candidates = 50
    ):
        self.inv_smt_solver = inv_smt_solver
        self.predicate_filtering = predicate_filtering
        self.generator = generator
        self.pipeline = pipeline
        self.formula_handler = formula_handler
        self.code_handler = code_handler

        self.presence_penalty_scale = presence_penalty_scale
        self.max_candidates = max_candidates
        
        self._result_file = self._get_result_file(result_file_path)
        self._logger = logging.getLogger(__name__)

        self.reset()

    def _get_result_file(self, result_file_path: str) -> io.TextIOWrapper:
        os.makedirs(os.path.dirname(result_file_path), exist_ok=True)
        return open(result_file_path, "w")

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
        
        self._log(f'Generate {len(self._fail_history)} counter examples, with {self._fail_history_hit} repeated fails')
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
        return solution, end_time, len(self._fail_history)
    
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
            self._reset_generator()
            self._curr_pipeline_step_index += 1
            self._curr_pipeline_step_time = time.time()
        
        return self.pipeline[self._curr_pipeline_step_index]
    
    def _get_presence_penalty(self) -> float:
        return math.tanh(self._fail_history_hit * self.presence_penalty_scale)
    
    def _predicate_filtering(self, candidates: list[str]) -> str:
        verify = False
        for candidate in candidates:
            self._log(f'Filtering predicates for candidate {candidate}')
            formula = self.formula_handler.extract_formula(candidate)
            filtered_predicates = self.predicate_filtering.filter(formula)
            for predicate in filtered_predicates:
                if predicate not in self._predicate_filtering_verify_set:
                    verify = True
                    self._log(f'Addind predicate {predicate} to verify set')
                self._predicate_filtering_verify_set[predicate] = True
            
        if verify:
            formula = ' && '.join([f'({predicate})' for predicate in self._predicate_filtering_verify_set.keys()])
            smt_lib2_formula = self.formula_handler.to_smt_lib2(formula)

            self._log(f'Verifying formula: {smt_lib2_formula}')
            self._log(f'For candidate: assert({formula})')
            counter_example = self.inv_smt_solver.get_counter_example(smt_lib2_formula)
            if counter_example is None:
                return f'assert({formula})'
    
    def _verify_candidates(self, candidates: list[str]) -> tuple[str, list[str]]:
        fails = []
        for candidate in candidates:
            self._log(f'Verifying candidate: {candidate}')

            if candidate in self._fail_history:
                self._fail_history_hit += 1
                fails.append((candidate, (self._fail_history[candidate])))
                self._log(f'Candidate already in fail history: {candidate}')
                continue

            formula = self.formula_handler.extract_formula(candidate)
            smt_lib2_formula = self.formula_handler.to_smt_lib2(formula)
            counter_example = self.inv_smt_solver.get_counter_example(smt_lib2_formula)
            if counter_example is None:
                return candidate, fails
            
            self._log(f'Candidate failed verification')
            fails.append((candidate, counter_example))
            
            self._log(f'Adding candidate to fail history: {candidate}')
            self._fail_history[candidate] = counter_example
        
        return None, fails

    def run(self, benchmark_id: str) -> tuple[str, float, int]:
        start_time = time.time()

        self._log(f'# Run Benchmark {benchmark_id}')

        self._log(f'Executing predicate filtering for preconditions')
        preconditions = self.code_handler.get_preconditions()
        solution = self._predicate_filtering(preconditions)
        if solution is not None:
            self._log(f'Predicate filtering found solution: {solution}')
            return self._handle_solution(solution, (time.time() - start_time))
        
        chat_options = ChatOptions()
        while True:
            llm, _ = self._next_pipeline_step()
            if llm is None:
                self._handle_solution(None, (time.time() - start_time))
                raise TimeoutError('Pipeline time exceeded')

            chat_options.presence_penalty = self._get_presence_penalty()
            
            self._log(f'Generating loop invariants candidates with model {llm} and presence penalty {chat_options.presence_penalty}')
            candidates = self.generator.generate(feedback=self._last_fails, llm=llm, chat_options=chat_options)
            self._log(f'Generated {len(candidates)} candidates')
            
            try:
                self._log(f'Verifying generated candidates')
                solution, self._last_fails = self._verify_candidates(candidates)
                if solution is not None:
                    return self._handle_solution(solution, (time.time() - start_time))

                self._log(f'Executing predicate filtering')
                solution = self._predicate_filtering(candidates)
                if solution is not None:
                    self._log(f'Predicate filtering found solution: {solution}')
                    return self._handle_solution(solution, (time.time() - start_time))
            except InvalidCodeFormulaError as e:
                self._log(f'Invalid candidate syntax')
                self._logger.error(e)
                continue
            except InvalidSMTLIB2FormulaError as e:
                self._log(f'Invalid SMT-LIB-2 formula syntax')
                self._logger.error(e)
                continue
            except InvalidCodeError as e:
                self._log(f'Invalid code while filtering predicates for candidate')
                self._logger.error(e)
                continue
            except TimeoutError as e:
                self._log(f'Timeout while verifying candidate')
                self._logger.error(e)
                continue

    def _reset_generator(self):
        self._log(f'Resetting generator')
        self._fail_history = {}
        self._fail_history_hit = 0
        self._last_fails = []
        self.generator.reset()
            
    def reset(self):
        self._predicate_filtering_verify_set = {}
        self._logs = []
        self._curr_pipeline_step_index = None
        self._curr_pipeline_step_time = None
        self._reset_generator()