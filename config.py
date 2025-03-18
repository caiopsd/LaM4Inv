import os
from dataclasses import dataclass

@dataclass
class Config:
    benchmarks_graph_path: str
    benchmarks_smt_path: str
    benchmarks_code_path: str

config = Config(
    benchmarks_graph_path="benchmarks/linear/c_graph/",
    benchmarks_smt_path="benchmarks/linear/c_smt2/",
    benchmarks_code_path="benchmarks/linear/c/",
)
