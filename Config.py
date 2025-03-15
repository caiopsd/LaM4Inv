from dataclasses import dataclass

@dataclass
class Config:
    benchmarks_graph_path: str
    benchmarks_smt_path: str
    benchmarks_c_path: str
    smt_check_timeout: int

config = Config(
    benchmarks_graph_path="benchmarks/linear/c_graph/",
    benchmarks_smt_path="benchmarks/linear/c_smt2/",
    benchmarks_c_path="benchmarks/linear/c/",
    smt_check_timeout=50
)
