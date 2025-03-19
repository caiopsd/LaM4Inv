import io
import os
import time

from smt.solver import InvalidFormulaError
from inv_smt_solver.inv_smt_solver import InvSMTSolver, CounterExample
from generator.generator import Generator
from formula_handler.formula_handler import FormulaHandler
from predicate_filtering.predicate_filtering import PredicateFiltering

class Runner:
    _fail_history: dict[str, CounterExample] = {}
    _generated_candidates: int = 0

    def __init__(
        self, 
        inv_smt_solver: InvSMTSolver, 
        predicate_filtering: PredicateFiltering,
        generator: Generator,
        formula_handler: FormulaHandler,
        result_file_path: str,
        inference_timeout: int,
        max_candidates: int = 50
    ):
        self.inv_smt_solver = inv_smt_solver
        self.predicate_filtering = predicate_filtering
        self.generator = generator
        self.formula_handler = formula_handler

        self.inference_timeout = inference_timeout
        self.max_candidates = max_candidates

        self.result_file = self._get_result_file(result_file_path)

    def _get_result_file(self, result_file_path: str) -> io.TextIOWrapper:
        os.makedirs(os.path.dirname(result_file_path), exist_ok=True)
        return open(result_file_path, "w")

    def _smt_verify(self, formula: str) -> CounterExample:
        smt_lib2_candidate = self.formula_handler.to_smt_lib2_assert(formula)
        counter_example = self.inv_smt_solver.get_counter_example(smt_lib2_candidate)
        if counter_example is not None:
            return counter_example

    def _bmc_verify(self, formula: str) -> str:
        filtered_predicates = self.predicate_filtering.filter(formula)
        for predicate in filtered_predicates:
            if self._smt_verify(predicate) is None:
                return predicate

    def _generate_candidates_from_feedback(self) -> list[str]:
        new_candidates = self.generator.generate(self._fail_history)
        self._generated_candidates += len(new_candidates)
        return new_candidates
    
    def _verify(self, candidates) -> str:
        for candidate in candidates:
            if candidate in self._fail_history:
                print(f'Candidate already in fail history: {candidate}')
                continue

            print(f'Verifying candidate: {candidate}')

            formula = self.formula_handler.extract_formula(candidate)
            try:
                counter_example = self._smt_verify(formula)
                if counter_example is None:
                    return candidate
                
                print(f'Counter example found: {counter_example}, trying predicate filtering')
                
                solution = self._bmc_verify(formula)
                if solution is not None:
                    return solution
            except InvalidFormulaError as e:
                print(f'Invalid candidate syntax: {candidate}')
                continue
            except TimeoutError as e:
                print(f'Timeout while verifying candidate: {candidate}')
                continue

            print(f'Verification failed, adding to fail history')
            
            self._fail_history[candidate] = counter_example
        
    def run(self) -> str:
        start_time = time.time()

        candidates = self.generator.generate()
        solution = self._verify(candidates)
        if solution is not None:
            return solution

        while self._generated_candidates < self.max_candidates:
            if time.time() - start_time >= self.inference_timeout:
                raise TimeoutError("Inference timeout")
            
            candidates = self._generate_candidates_from_feedback()
            solution = self._verify(candidates)
            if solution is not None:
                return solution

        return None
