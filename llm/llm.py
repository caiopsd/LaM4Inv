from abc import ABC, abstractmethod

class LLM(ABC):
    @abstractmethod
    def prompt(self, prompt: str) -> str:
        pass