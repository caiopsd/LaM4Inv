import z3

from smt.smt import Solver, SatStatus
from utils.run_with_timeout import run_with_timeout, TimeoutException

class Z3Solver(Solver):
    def __init__(self, timeout: int):
        self.solver = z3.Solver()
        self.solver.set(auto_config=False)
        self.timeout = timeout
        self.solver.set('timeout', self.timeout)

    def check(self, formula: str) -> SatStatus:
        self.solver.reset()
        try:
            decl = z3.parse_smt2_string(formula)
        except:
            self.logger.debug("Invalid SMTLIB2 formula: %s", formula)
            return None, False
        
        self.solver.add(decl)
        try:
            res = run_with_timeout(self.solver.check, timeout=self.timeout)
        except TimeoutException:
            return SatStatus.UNKNOWN
        
        if res == z3.sat:
            return SatStatus.SAT
        elif res == z3.unsat:
            return SatStatus.UNSAT
        else:
            return SatStatus.UNKNOWN

    def model(self) -> str:
        return str(self.solver.model())