from enum import Enum

class CounterExampleKind(Enum):
    NEGATIVE = 0
    POSITIVE = 1
    INTERMEDIATE = 2

class CounterExample:
    def __init__(self, assignment: str, kind: CounterExampleKind = None):
        self.kind = kind
        self.assignment = assignment
