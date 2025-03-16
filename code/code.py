from abc import ABC, abstractmethod

class Code(ABC):
    @abstractmethod
    def extract_loop_preconditions(self) -> list[str]:
        pass