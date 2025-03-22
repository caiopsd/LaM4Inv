import argparse
import os
import logging
import re
from dotenv import load_dotenv

from runner import Runner
from config import config
from smt.z3_solver import Z3Solver
from inv_smt_solver.inv_smt_solver import InvSMTSolver
from llm.llm import LLM
from llm.openai import OpenAI, ChatGPTModel, DeepseekModel
from llm.transformers import LlamaModel, Transformers
from generator.generator import Generator
from code_handler.c_code_handler import CCodeHandler
from code_handler.code_handler import CodeHandler
from code_handler.c_formula_handler import CFormulaHandler
from bmc.esbmc import ESBMC
from bmc.bmc import BMC
from predicate_filtering.predicate_filtering import PredicateFiltering

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

chatgpt_models = [model.value for model in list(ChatGPTModel)]
llama_models = [model.value for model in list(LlamaModel)]
deepseek_models = [model.value for model in list(DeepseekModel)]
all_models = chatgpt_models + llama_models + deepseek_models

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
    candidates_pattern = re.compile(r'Verified candidates: (\d+)')
    
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
        f.write(f"Average time: {mean_time:.2f} seconds\n")
        f.write(f"Average verified candidates: {mean_candidates:.2f}\n")
                
def run_experiment(
        start: int, 
        end: int, 
        inference_timeout: int,
        results_path: str,
        z3_solver: Z3Solver, 
        pipeline: list[tuple[LLM, float]],
        bmc: BMC
):
    for i in range(start, end):
        graph_file_path = os.path.join(config.benchmarks_graph_path, f'{i}.c.json')
        smt_file_path = os.path.join(config.benchmarks_smt_path, f'{i}.c.smt')
        code_file_path = os.path.join(config.benchmarks_code_path, f'{i}.c')
        sample_result_file_path = os.path.join(results_path, f'{i}.txt')

        code_handler = get_code_handler(code_file_path)
        formula_handler = CFormulaHandler()
        z3_inv_smt_solver = InvSMTSolver(z3_solver, smt_file_path)
        generator = Generator(code_handler)
        predicate_filtering = PredicateFiltering(code_handler, formula_handler, bmc)
        runner = Runner(
            inv_smt_solver=z3_inv_smt_solver, 
            predicate_filtering=predicate_filtering, 
            generator=generator, 
            pipeline=pipeline,
            formula_handler=formula_handler, 
            result_file_path=sample_result_file_path, 
            inference_timeout=inference_timeout,
            max_verified_candidates=50,
            presence_penalty_scale=0.2
        )

        try:
            runner.run(i)
        except TimeoutError:
            continue

    write_result(results_path)

def get_llm(model:str):
    if model in chatgpt_models:
        if OPENAI_API_KEY is None:
            raise ValueError("OPENAI_API_KEY environment variable must be set")
        return OpenAI(ChatGPTModel(model), OPENAI_API_KEY)
    if model in llama_models:
        return Transformers(LlamaModel(model))
    if model in deepseek_models:
        if DEEPSEEK_API_KEY is None:
            raise ValueError("DEEPSEEK_API_KEY environment variable must be set")
        return OpenAI(DeepseekModel(model), DEEPSEEK_API_KEY, base_url=config.deepseek_api_url)

def parse_range(value):
    try:
        start, end = value.split("-")
        start = int(start)
        end = int(end)
        if start > end:
            raise argparse.ArgumentTypeError("Start value must be less than end value")
        return (start, end)
    except ValueError:
        raise argparse.ArgumentTypeError("Range must be in the form of start-end")
    
def parse_pipeline(input: str):
    pipeline = []
    for step in input.split(";"):
        model, threshold = step.split(",")
        model = model.strip()
        threshold = float(threshold.strip())
        if threshold > 1 or threshold < 0:
            raise argparse.ArgumentTypeError("The threshold value must be between 0 and 1")
        pipeline.append((model, threshold))
    return pipeline

def main():
    parser = argparse.ArgumentParser(description="Run benchmarks")

    parser.add_argument("--pipeline", type=parse_pipeline, default=f'{ChatGPTModel.GPT_4O.value}, 0;{DeepseekModel.DEEPSEEK_R1}, 0.5', help="Pipeline of LLM models with their activation thresholds, formatted as: model, threshold; model, threshold;... Example: gpt-4,0;deepseek,0.5")
    parser.add_argument("--benchmark-range", type=parse_range, default="228-229", help="Range of benchmark indices in the format a-b. Represents the interval (a, b].")
    parser.add_argument("--inference-timeout", type=int, default=600, help="Timeout for the loop invariant inference")
    parser.add_argument("--results-path", type=str, default="results/test", help="Output directory for results")
    parser.add_argument("--smt-timeout", type=int, default=50, help="Timeout for the SMT check")
    parser.add_argument("--bmc-timeout", type=float, default=5, help="Timeout for predicate filtering")
    parser.add_argument("--bmc-max-steps", type=int, default=10, help="Maximum number of steps for BMC")
    parser.add_argument("--log-level", type=str, default="ERROR", choices=["INFO", "CRITICAL", "ERROR", "WARNING", "DEBUG"], help="Logging level")

    args = parser.parse_args()

    logging.basicConfig(level=args.log_level)

    benchmark_range = args.benchmark_range

    pipeline = [(get_llm(model), threshold) for model, threshold in args.pipeline]
    z3_solver = Z3Solver(args.smt_timeout)
    esbmc = ESBMC(config.esbmc_bin_path, args.bmc_timeout, args.bmc_max_steps)

    run_experiment(benchmark_range[0], benchmark_range[1], args.inference_timeout, args.results_path,  z3_solver, pipeline, esbmc)

if __name__ == "__main__":
    main()
