import argparse
import os
import logging
import re
from dotenv import load_dotenv
from pydantic import BaseModel

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

class ModelResults(BaseModel):
    solutions_found: int = 0
    solutions_found_by_model: int = 0
    average_runtime: float = 0
    average_counter_examples: float = 0
    average_repeated_fails: float = 0

def get_code_handler(code_file_path: str) -> CodeHandler:
    with open(code_file_path, "r") as f:
        code = f.read()
    return CCodeHandler(code)

def update_model_statistics(content: str, results: ModelResults):
    counter_examples_generated_pattern = re.compile(r'(\d+) counter examples were generated for the model proposals, with (\d+) repeated fails')
    model_run_time_pattern = re.compile(r'The model runtime was ([\d.]+) seconds')

    mean_counter_examples_generated_match = counter_examples_generated_pattern.search(content)
    if not mean_counter_examples_generated_match:
        raise ValueError("Counter examples generated not found")
    mean_counter_examples_generated = int(mean_counter_examples_generated_match.group(1))
    repeated_fails = int(mean_counter_examples_generated_match.group(2))

    model_runtime_match = model_run_time_pattern.search(content)
    if not model_runtime_match:
        raise ValueError("Model runtime not found")
    model_runtime = float(model_runtime_match.group(1))

    results.average_runtime = (results.average_runtime * (results.solutions_found - 1) + model_runtime) / results.solutions_found
    results.average_counter_examples = (results.average_counter_examples * (results.solutions_found - 1) + mean_counter_examples_generated) / results.solutions_found
    results.average_repeated_fails = (results.average_repeated_fails * (results.solutions_found - 1) + repeated_fails) / results.solutions_found

def write_result(result_path: str):
    total_benchmarks = 0
    solutions = 0
    predicate_filtering_solutions = 0
    average_runtime = 0
    model_results:dict[str,ModelResults] = {}
    fails = []

    solution_found_by_predicate_filtering_pattern = re.compile(r'Solution found by the predicate filtering mechanism using the (.+) model: (.+)')
    solution_found_by_llm_pattern = re.compile(r'Solution found by the ([\w-]+) model: (.+)')
    total_runtime_pattern = re.compile(r'The total runtime was ([\d.]+) seconds')
    
    for result_file in os.listdir(result_path):
        if not result_file.endswith('.txt') or result_file == 'result.txt':
            continue
            
        total_benchmarks += 1

        file_path = os.path.join(result_path, result_file)
        with open(file_path, "r") as f:
            content = f.read()
            
            solution_found_by_predicate_filtering_match = solution_found_by_predicate_filtering_pattern.search(content)
            solution_found_by_llm_match = solution_found_by_llm_pattern.search(content)

            if solution_found_by_predicate_filtering_match or solution_found_by_llm_match :
                solutions += 1
            else:
                fails.append(result_file[:-4])

            if solution_found_by_predicate_filtering_match:
                predicate_filtering_solutions += 1
                
                model = solution_found_by_predicate_filtering_match.group(1)
                if model not in model_results:
                    model_results[model] = ModelResults()
                results = model_results[model]
                results.solutions_found += 1
                update_model_statistics(content, results)
            
            if solution_found_by_llm_match:
                model = solution_found_by_llm_match.group(1)
                if model not in model_results:
                    model_results[model] = ModelResults()
                results = model_results[model]
                results.solutions_found += 1
                results.solutions_found_by_model += 1
                update_model_statistics(content, results)
                
            runtime_match = total_runtime_pattern.search(content)
            if runtime_match:
                runtime = float(runtime_match.group(1))
                average_runtime = (average_runtime * (total_benchmarks - 1) + runtime) / total_benchmarks

                
    success_rate = (solutions / total_benchmarks) * 100 if total_benchmarks > 0 else 0
    
    with open(os.path.join(result_path, 'result.txt'), "w") as f:
        f.write(f"Total benchmarks: {total_benchmarks}\n")
        f.write(f"Solutions found: {solutions}\n")
        f.write(f"Solutions found by predicate filtering: {predicate_filtering_solutions}\n")
        f.write(f"Success rate: {success_rate:.2f}%\n")
        f.write(f"Average runtime: {average_runtime:.2f} seconds\n")

        if fails:
            f.write(f"Fails: {', '.join(fails)}\n")

        for model in model_results:
            results = model_results[model]
            f.write(f"\nModel: {model}\n")
            f.write(f"Solutions found: {results.solutions_found}\n")
            f.write(f"Solutions found by model: {results.solutions_found_by_model}\n")
            f.write(f"Average runtime: {results.average_runtime:.2f} seconds\n")
            f.write(f"Average counter examples: {results.average_counter_examples:.2f}\n")
            f.write(f"Average repeated fails: {results.average_repeated_fails:.2f}\n")
                
def run_experiment(
        benchmarks: list[int],
        results_path: str,
        z3_solver: Z3Solver, 
        pipeline: list[tuple[LLM, float]],
        bmc: BMC,
        max_chat_interactions: int
):
    for i in benchmarks:
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
            code_handler=code_handler, 
            result_file_path=sample_result_file_path, 
            presence_penalty_scale=0.2,
            max_chat_interactions=max_chat_interactions
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
    raise ValueError(f"Model {model} not found")

def parse_range(value: str):
    itens = value.split(",")
    benchmarks = []
    for item in itens:
        if "-" in item:
            start, end = item.split("-")
            benchmarks.extend(range(int(start.strip()), int(end.strip()) + 1))
        else:
            benchmarks.append(int(item.strip()))
    return benchmarks
    
def parse_pipeline(input: str):
    pipeline = []
    for step in input.split(";"):
        model, timeout = step.split(",")
        model = model.strip()
        if model not in all_models:
            raise argparse.ArgumentTypeError(f"Model {model} not found")
        timeout = float(timeout.strip())
        pipeline.append((model, timeout))
    return pipeline

def main():
    parser = argparse.ArgumentParser(description="Run benchmarks")

    parser.add_argument("--mode", type=str, default="run", choices=["run", "evaluate"], help="Mode of operation. 'run' runs the benchmarks, 'evaluate' evaluates the existing results")
    parser.add_argument("--pipeline", type=parse_pipeline, default=f'{ChatGPTModel.GPT_4O.value}, 0; {ChatGPTModel.GPT_4O_MINI.value}, 40; {ChatGPTModel.O3_MINI.value}, 300; {DeepseekModel.DEEPSEEK_R1.value}, 600', help="Pipeline of LLM models with their timeouts in seconds, formatted as: model, timeout; model, timeout;... Example: gpt-4,120;deepseek,300")
    parser.add_argument("--benchmarks", type=parse_range, default="1-316", help="Benchmarks to run. Specify a list of individual numbers and/or numeric ranges formatted as a-b. Examples: 1,2,3, 1,2,3-5, or 5-10.")
    parser.add_argument("--results-path", type=str, default="results/test", help="Output directory for results")
    parser.add_argument("--smt-timeout", type=int, default=50, help="Timeout for the SMT check")
    parser.add_argument("--bmc-timeout", type=float, default=5, help="Timeout for BMC")
    parser.add_argument("--bmc-max-steps", type=int, default=10, help="Maximum number of steps for BMC")
    parser.add_argument("--log-level", type=str, default="INFO", choices=["INFO", "CRITICAL", "ERROR", "WARNING", "DEBUG"], help="Logging level")
    parser.add_argument("--max-chat-interactions", type=int, default=-1, help="Max chat interactions with the LLM model")

    args = parser.parse_args()

    if args.mode == "evaluate":
        write_result(args.results_path)
        return

    logging.basicConfig(level=args.log_level)

    pipeline = [(get_llm(model), threshold) for model, threshold in args.pipeline]
    z3_solver = Z3Solver(args.smt_timeout)
    esbmc = ESBMC(config.esbmc_bin_path, args.bmc_timeout, args.bmc_max_steps)

    run_experiment(args.benchmarks, args.results_path,  z3_solver, pipeline, esbmc, args.max_chat_interactions)

if __name__ == "__main__":
    main()
