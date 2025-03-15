from abc import ABC, abstractmethod

from inv_smt_solver.counter_example import CounterExample

class InvSMTSolver(ABC):
    @abstractmethod
    def verify(self, inv: str) -> tuple[CounterExample, bool]:
        pass