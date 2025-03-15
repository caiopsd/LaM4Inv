from inv_smt_solver.inv_smt_solver import SMTSolver

class Runner:
    def __init__(self, smt_solver: SMTSolver):
        self.smt = smt_solver

    def run(self, graph_file_path: str, smt_file_path: str, c_file_path: str, result_file_path: str):
        result_file = open(result_file_path, "w")
