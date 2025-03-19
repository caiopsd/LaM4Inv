import io
import os
import time
import queue

from smt.solver import InvalidFormulaError
from inv_smt_solver.inv_smt_solver import InvSMTSolver, CounterExample
from generator.generator import Generator
from formula_handler.formula_handler import FormulaHandler
from predicate_filtering.predicate_filtering import PredicateFiltering

class Runner:
    _fail_history: dict[str, CounterExample] = {}
    _verify_queue: queue.Queue = queue.Queue()
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
    
    def _insert_candidates_to_verify(self, candidates: list[str]):
        if self._generated_candidates >= self.max_candidates:
            return
        
        for candidate in candidates:
            if candidate not in self._fail_history and candidate not in self._verify_queue.queue:
                self._verify_queue.put(candidate)
                self._generated_candidates += 1

    def _verify(self) -> tuple[str, CounterExample]:
        if self._verify_queue.empty():
            return
        
        candidate = self._verify_queue.get()
        candidate_formula = self.formula_handler.extract_formula(candidate)
        smt_lib2_candidate = self.formula_handler.to_smt_lib2_assert(candidate_formula)
        counter_example = self.inv_smt_solver.get_counter_example(smt_lib2_candidate)
        if counter_example is None:
            return candidate, None
        
        filtered_predicates = self.predicate_filtering.filter(candidate_formula)
        for predicate in filtered_predicates:
            smt_lib2_candidate = self.formula_handler.to_smt_lib2_assert(predicate)
            counter_example = self.inv_smt_solver.get_counter_example(smt_lib2_candidate)
            if counter_example is None:
                return candidate, None

        self._fail_history[candidate] = counter_example

        return candidate, counter_example

    def _generate_candidates_from_feedback(self):
        new_candidates = self.generator.generate(self._fail_history)
        self._insert_candidates_to_verify(new_candidates)
        
    def run(self) -> str:
        start_time = time.time()

        candidates = self.generator.generate()
        self._insert_candidates_to_verify(candidates)

        while not self._verify_queue.empty():
            if time.time() - start_time >= self.inference_timeout:
                raise TimeoutError("Inference timeout")
            
            try:
                candidate, counter_example = self._verify()
                if counter_example is None:
                    return candidate
            except InvalidFormulaError as e:
                print(f'Invalid candidate: {e}')
                continue
            except TimeoutError as e:
                print(f'Timeout while verifying candidate: {e}')
                continue
            
            print(f'Verified candidate: {candidate}')
            print(f'Found counter example:\n{counter_example}')
            print(f'Counter example kind is {counter_example.kind.value}')

            self._generate_candidates_from_feedback()

        return None
