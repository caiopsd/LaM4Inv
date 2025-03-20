import argparse
import os
import io
import time
import re
from dotenv import load_dotenv

from runner import Runner
from config import config
from smt.z3_solver import Z3Solver
from inv_smt_solver.inv_smt_solver import InvSMTSolver
from llm.llm import LLM
from llm.openai import OpenAI, ChatGPTModel, LlamaModel
from generator.generator import Generator
from code_handler.c_code_handler import CCodeHandler
from code_handler.code_handler import CodeHandler
from code_handler.c_formula_handler import CFormulaHandler
from bmc.esbmc import ESBMC
from bmc.bmc import BMC
from predicate_filtering.predicate_filtering import PredicateFiltering

load_dotenv()

def valid_range(value):
    try:
        start, end = value.split("-")
        start = int(start)
        end = int(end)
        if start > end:
            raise argparse.ArgumentTypeError("Start value must be less than end value")
        return value
    except ValueError:
        raise argparse.ArgumentTypeError("Range must be in the form of start-end")


def get_code_handler(code_file_path: str) -> CodeHandler:
    with open(code_file_path, "r") as f:
        code = f.read()
    return CCodeHandler(code)

def write_result(result_path: str):
    total_benchmarks = 0
    successful_solutions = 0
    total_time = 0
    total_candidates = 0
    
    # Regex patterns
    solution_pattern = re.compile(r'Solution: (.+)')
    no_solution_pattern = re.compile(r'Solution: no solution found')
    run_time_pattern = re.compile(r'Run time: ([\d.]+)')
    candidates_pattern = re.compile(r'Generated candidates: (\d+)')
    
    # Process each result file
    for result_file in os.listdir(result_path):
        if not result_file.endswith('.txt') or result_file == 'result.txt':
            continue
            
        total_benchmarks += 1
        file_path = os.path.join(result_path, result_file)
        
        with open(file_path, "r") as f:
            content = f.read()
            
            solution_match = solution_pattern.search(content)
            no_solution_match = no_solution_pattern.search(content)
            
            if solution_match and not no_solution_match:
                successful_solutions += 1
                
            run_time_match = run_time_pattern.search(content)
            if run_time_match:
                time_spent = float(run_time_match.group(1))
                total_time += time_spent
                
            candidates_match = candidates_pattern.search(content)
            if candidates_match:
                candidates_generated = int(candidates_match.group(1))
                total_candidates += candidates_generated
    
    success_rate = (successful_solutions / total_benchmarks) * 100 if total_benchmarks > 0 else 0
    mean_time = total_time / total_benchmarks if total_benchmarks > 0 else 0
    mean_candidates = total_candidates / total_benchmarks if total_benchmarks > 0 else 0
    
    with open(os.path.join(result_path, 'result.txt'), "w") as f:
        f.write(f"Total benchmarks: {total_benchmarks}\n")
        f.write(f"Successful solutions: {successful_solutions}\n")
        f.write(f"Success rate: {success_rate:.2f}%\n")
        f.write(f"Mean time: {mean_time:.2f} seconds\n")
        f.write(f"Mean generated candidates: {mean_candidates:.2f}\n")
                
def run_experiment(
        start: int, 
        end: int, 
        inference_timeout: int,
        results_path: str,
        z3_solver: Z3Solver, 
        llm: LLM,
        bmc: BMC
):
    results = []
    for i in range(start, end):
        graph_file_path = os.path.join(config.benchmarks_graph_path, f'{i}.c.json')
        smt_file_path = os.path.join(config.benchmarks_smt_path, f'{i}.c.smt')
        code_file_path = os.path.join(config.benchmarks_code_path, f'{i}.c')
        sample_result_file_path = os.path.join(results_path, f'{i}.txt')

        code_handler = get_code_handler(code_file_path)
        formula_handler = CFormulaHandler()
        z3_inv_smt_solver = InvSMTSolver(z3_solver, smt_file_path)
        generator = Generator(llm, z3_solver, code_handler)
        predicate_filtering = PredicateFiltering(code_handler, formula_handler, bmc)
        runner = Runner(z3_inv_smt_solver, predicate_filtering, generator, formula_handler, sample_result_file_path, inference_timeout=inference_timeout)

        llm.clear()

        solution, run_time, generated_candidates = runner.run()
        results.append((i, solution, run_time, generated_candidates))

        runner.close()

    write_result(results_path)

def main():
    parser = argparse.ArgumentParser(description="Run benchmarks")

    chat_gpt_models = [model.value for model in list(ChatGPTModel)]
    llama_models = [model.value for model in list(LlamaModel)]

    parser.add_argument("--llm-model", type=str, default=ChatGPTModel.GPT_4O.value, help="LLM model to use", choices=chat_gpt_models+llama_models)
    parser.add_argument("--benchmark-range", type=valid_range, default="228-229", help="Range of benchmarks to run")
    parser.add_argument("--smt-timeout", type=int, default=50, help="Timeout for SMT check")
    parser.add_argument("--inference-timeout", type=int, default=600, help="Timeout for LLM inference")
    parser.add_argument("--results-path", type=str, default="results/test", help="Output directory for results")
    parser.add_argument("--bmc-timeout", type=float, default=5, help="Timeout for BMC")
    parser.add_argument("--bmc-max-steps", type=int, default=10, help="Maximum number of steps for BMC")
    parser.add_argument("--log-level", type=str, default="INFO", choices=["INFO", "CRITICAL", "ERROR", "WARNING", "DEBUG"], help="Logging level")
    
    args = parser.parse_args()
    benchmark_range = [int(x) for x in args.benchmark_range.split("-")]

    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    if args.llm_model in chat_gpt_models:
        if OPENAI_API_KEY is None:
            raise ValueError("OPENAI_API_KEY environment variable must be set")
        model = ChatGPTModel(args.llm_model)
        llm = OpenAI(model, OPENAI_API_KEY)
    if args.llm_model in llama_models:
        model = LlamaModel(args.llm_model)
        llm = OpenAI(model)
    z3_solver = Z3Solver(args.smt_timeout)
    esbmc = ESBMC(config.esbmc_bin_path, args.bmc_timeout, args.bmc_max_steps)

    run_experiment(benchmark_range[0], benchmark_range[1], args.inference_timeout, args.results_path,  z3_solver, llm, esbmc)

if __name__ == "__main__":
    main()
