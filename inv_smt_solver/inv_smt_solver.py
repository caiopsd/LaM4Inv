import logging
import re

from smt.solver import Solver, SatStatus
from inv_smt_solver.counter_example import CounterExample, CounterExampleKind

class InvSMTSolver:
    def __init__(self, solver: Solver, smt_file_path: str):
        self.solver = solver
        self._init_tpl(smt_file_path)
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

    def _get_precondition_counter_example(self, inv: str) -> CounterExample:
        formula = self.tpl[0] + self._get_inv_condition(inv) + self.tpl[1]
        res = self.solver.check(formula)
        if res == SatStatus.SAT:
            assignments = self.solver.get_assignments()
            filtered_assignments = {
                decl: assignments[decl]
                for decl in assignments if not self._is_ignored_variable(decl)
            }
            return CounterExample(filtered_assignments, CounterExampleKind.POSITIVE)
        elif res == SatStatus.UNKNOWN:
            raise TimeoutError(inv)
        
        assert res == SatStatus.UNSAT
        return None
            
    def _get_transition_counter_example(self, inv: str) -> CounterExample:
        formula = self.tpl[0] + self._get_inv_condition(inv) + self.tpl[2]
        res = self.solver.check(formula)
        if res == SatStatus.SAT:
            assignments = self.solver.get_assignments()
            filtered_assignments = {
                decl: assignments[decl]
                for decl in assignments if not self._is_ignored_variable(decl)
            }
            return CounterExample(filtered_assignments, CounterExampleKind.INTERMEDIATE)
        elif res == SatStatus.UNKNOWN:
            raise TimeoutError(inv)
        
        assert res == SatStatus.UNSAT
        return None

    def _get_postcondition_counter_example(self, inv: str) -> CounterExample:
        formula = self.tpl[0] + self._get_inv_condition(inv) + self.tpl[3]
        res = self.solver.check(formula)
        if res == SatStatus.SAT:
            assignments = self.solver.get_assignments()
            filtered_assignments = {
                x: assignments[x]
                for x in assignments if not self._is_ignored_variable(x)
            }
            return CounterExample(filtered_assignments, CounterExampleKind.NEGATIVE)
        elif res == SatStatus.UNKNOWN:
            raise TimeoutError(inv)
        
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