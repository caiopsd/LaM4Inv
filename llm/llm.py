from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class ChatOptions:
    presence_penalty: float = None

class LLM(ABC):
    @abstractmethod
    def chat(self, message: str, options: ChatOptions = None) -> str:
        pass

    @abstractmethod
    def clear(self):
        pass