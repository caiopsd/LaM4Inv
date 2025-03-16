import logging
import re

from smt.smt import Solver, SatStatus
from inv_smt_solver.counter_example import CounterExample, CounterExampleKind

class InvSMTSolver:
    def __init__(self, solver: Solver, smt_file_path: str):
        self.solver = solver
        self.tpl = self._init_tpl(smt_file_path)
        self.logger = logging.getLogger(__name__)

    def _init_tpl(self, smt_file_path: str) -> list[str]:
        with open(smt_file_path, 'r') as smt_file:
            vc_sections = smt_file.read().split("SPLIT_HERE_asdfghjklzxcvbnmqwertyuiop")
        assert len(vc_sections) == 5

        self.tpl = [
            vc_sections[0], 
            vc_sections[1] + vc_sections[2],
            vc_sections[1] + vc_sections[3],
            vc_sections[1] + vc_sections[4]
        ]

    def _get_inv_condition(self, inv: str) -> str:
        return inv[7:-1]

    def _is_ignored_variable(self, variable: str) -> bool:
        pattern = re.compile(r'^(inv-f|post-f|pre-f|trans-f|div0|mod0|.*_.*)$')
        return bool(pattern.match(variable))

    def _get_precondition_counter_example(self, inv: str) -> tuple[CounterExample, bool]:
        formula = self.tpl[0] + self._get_inv_condition(inv) + self.tpl[1]
        res = self.solver.check(formula)
        ce = CounterExample()
        if res == SatStatus.SAT:
            model = self.solver.model()
            ce.assignment = {str(x): str(model[x]) for x in model if not self._is_ignored_variable(str(x))}
            ce.kind = CounterExampleKind.POSITIVE
            return ce, True
        elif res == SatStatus.UNKNOWN:
            raise TimeoutError("SMT check timed out while verifying precondition for invariant: %s" % inv)
        
        assert res == SatStatus.UNSAT
        return None
            
    def _get_transition_counter_example(self, inv: str) -> tuple[CounterExample, bool]:
        formula = self.tpl[0] + self._get_inv_condition(inv) + self.tpl[2]
        res = self.solver.check(formula)
        ce = CounterExample()
        if res == SatStatus.SAT:
            model = self.solver.model()
            ce.assignment = (
                {str(x).rstrip("!"): str(model[x]) for x in model if not self._is_ignored_variable(str(x)) and not str(x).endswith("!")},
                {str(x).rstrip("!"): str(model[x]) for x in model if not self._is_ignored_variable(str(x)) and str(x).endswith("!")}
            )
            ce.kind = CounterExampleKind.INTERMEDIATE
        elif res == SatStatus.UNKNOWN:
            raise TimeoutError("SMT check timed out while verifying precondition for invariant: %s" % inv)
        
        assert res == SatStatus.UNSAT
        return None

    def _get_postcondition_counter_example(self, inv: str) -> tuple[CounterExample, bool]:
        formula = self.tpl[0] + self._get_inv_condition(inv) + self.tpl[3]
        res = self.solver.check(formula)
        ce = CounterExample()
        if res == SatStatus.SAT:
            model = self.solver.model()
            ce.assignment = {str(x): str(model[x]) for x in model if not self._is_ignored_variable(str(x))}
            ce.kind = CounterExampleKind.NEGATIVE
            return ce
        elif res == SatStatus.UNKNOWN:
            raise TimeoutError("SMT check timed out while verifying precondition for invariant: %s" % inv)
        
        assert res == SatStatus.UNSAT
        return None

    def get_counter_example(self, inv: str) -> CounterExample:
        precondition_ce = self._get_precondition_counter_example(inv)
        if precondition_ce:
            return precondition_ce
        
        transition_ce = self._get_transition_counter_example(inv)
        if transition_ce:
            return transition_ce
        
        postcondition_ce = self._get_postcondition_counter_example(inv)
        if postcondition_ce:
            return postcondition_ce
        
        return None