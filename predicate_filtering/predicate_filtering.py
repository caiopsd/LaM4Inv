from inv_smt_solver.inv_smt_solver import InvSMTSolver

class PredicateFiltering:
    def __init__(self, inv_smt_solver: InvSMTSolver):
        self.inv_smt_solver = inv_smt_solver

    def filter(self, expression: str) -> list[str]:
        pass