from abc import ABC, abstractmethod
from conde_handler.language import Language

class CodeHandler(ABC):
    @abstractmethod
    def assert_to_smt_lib2(self, assertion: str) -> str:
        pass

    @abstractmethod
    def get_code(self) -> str:
        pass

    @abstractmethod
    def get_language(self) -> Language:
        pass

    @abstractmethod
    def get_assert_format(self) -> str:
        pass

    @abstractmethod
    def get_assert_pattern(self) -> str:
        pass
