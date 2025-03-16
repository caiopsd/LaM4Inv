from abc import ABC, abstractmethod
from enum import Enum

class SatStatus(Enum):
    SAT = 1
    UNSAT = 2
    UNKNOWN = 3

class Solver(ABC):
    @abstractmethod
    def check(self, formula: str, timeout: int = None) -> SatStatus:
        pass
    
    @abstractmethod
    def model(self) -> str:
        pass

    @abstractmethod
    def is_valid_expression(self, expression: str) -> bool:
        pass