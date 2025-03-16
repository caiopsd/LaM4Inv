import io
import os
import time
import queue
from enum import Enum

from inv_smt_solver.inv_smt_solver import InvSMTSolver, CounterExample
from generator.generator import Generator

class Runner:
    _fail_history: list[tuple[str, CounterExample]] = []
    _verify_queue: queue.Queue = queue.Queue()
    _generated_candidates: int = 0

    def __init__(
        self, 
        inv_smt_solver: InvSMTSolver, 
        generator: Generator,
        code_file_path: str, 
        result_file_path: str,
        inference_timeout: int,
        max_candidates: int = 50
    ):
        self.inv_smt_solver = inv_smt_solver
        self.generator = generator

        self.inference_timeout = inference_timeout
        self.max_candidates = max_candidates

        self.result_file = self._get_result_file(result_file_path)
        with open(code_file_path, 'r') as f:
            self.code = f.read()

    def _get_result_file(result_file_path: str) -> io.TextIOWrapper:
        os.makedirs(os.path.dirname(result_file_path), exist_ok=True)
        return open(result_file_path, "w")
    
    def _insert_candidates_to_verify(self, candidates: list[str]):
        if self._generated_candidates >= self.max_candidates:
            return
        
        for candidate in candidates:
            self._verify_queue.put(candidate)
            self._generated_candidates += 1

    def _verify(self) -> tuple[str, CounterExample]:
        if self._verify_queue.empty():
            return
        
        candidate = self._verify_queue.get()
        counter_example = self.inv_smt_solver.get_counter_example(candidate)
        if counter_example is None:
            return candidate, None
        self._fail_history.append((candidate, counter_example))

        return candidate, counter_example

    def _generate_candidates_from_feedback(self):
        new_candidates = self.generator.generate(self.code, self._fail_history)
        self._insert_candidates_to_verify(new_candidates)
        
    def run(self) -> str:
        start_time = time.time()

        candidates = self.generator.generate(self.code)
        self._insert_candidates_to_verify(candidates)

        while not self._verify_queue.empty():
            if time.time() - start_time >= self.inference_timeout:
                raise TimeoutError("Inference timeout")
            
            candidate, counter_example = self._verify()
            if counter_example is None:
                return candidate

            self._generate_candidates_from_feedback()

        return None