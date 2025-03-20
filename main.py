import argparse
import os
import io
import time
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

def get_result_file(results_path: str) -> io.TextIOWrapper:
    os.makedirs(results_path, exist_ok=True)
    return open(os.path.join(results_path, 'result.txt'), "a")

def get_code_handler(code_file_path: str) -> CodeHandler:
    with open(code_file_path, "r") as f:
        code = f.read()
    return CCodeHandler(code)

def write_result(result_file: io.TextIOWrapper, message: str):
    formmated_time = time.strftime("%H:%M:%S %d/%m/%Y", time.gmtime(time.time()))
    print(f'{formmated_time} {message}')
    result_file.write(f'{formmated_time} {message}\n')

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
    result_file = get_result_file(results_path)
    write_result(result_file, "# Experiment")
    for i in range(start, end):
        graph_file_path = os.path.join(config.benchmarks_graph_path, f'{i}.c.json')
        smt_file_path = os.path.join(config.benchmarks_smt_path, f'{i}.c.smt')
        code_file_path = os.path.join(config.benchmarks_code_path, f'{i}.c')
        sample_result_file_path = os.path.join(results_path, f'{i}.txt')

        write_result(result_file, f"## {i}")

        code_handler = get_code_handler(code_file_path)
        formula_handler = CFormulaHandler()
        z3_inv_smt_solver = InvSMTSolver(z3_solver, smt_file_path)
        generator = Generator(llm, z3_solver, code_handler)
        predicate_filtering = PredicateFiltering(code_handler, formula_handler, bmc)
        runner = Runner(z3_inv_smt_solver, predicate_filtering, generator, formula_handler, sample_result_file_path, inference_timeout=inference_timeout)

        llm.clear()

        solution, run_time, generated_candidates = runner.run()
        results.append((i, solution, run_time, generated_candidates))

        write_result(result_file, f"Run time: {run_time}")
        write_result(result_file, f"Generated candidates: {generated_candidates}")
        if solution is not None:
            write_result(result_file, f"Solution: {solution}\n")
        else:
            write_result(result_file, "No solution found\n")

        runner.close()

    mean_time = sum([result[2] for result in results]) / len(results) if results else 0
    mean_generated_candidates = sum([result[3] for result in results]) / len(results) if results else 0
    solutions = [result[1] for result in results if result[1] is not None]

    write_result(result_file, "# Summary")
    write_result(result_file, f"Total benchmarks: {len(results)}")
    write_result(result_file, f"Solutions: {len(solutions)}")
    write_result(result_file, f'Success rate: {len(solutions) / len(results) * 100}%')
    write_result(result_file, f"Mean run time: {mean_time}")
    write_result(result_file, f"Mean generated candidates: {mean_generated_candidates}")
    
    result_file.close()

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
