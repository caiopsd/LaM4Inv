import argparse
import os
import io

from dotenv import load_dotenv

load_dotenv()

from runner import Runner
from config import config
from smt.z3_solver import Z3Solver
from inv_smt_solver.inv_smt_solver import InvSMTSolver
from llm.chatgpt import ChatGPT, ChatGPTModel
from llm.llama import Llama, LlamaModel
from generator.generator import Generator

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

def run_experiment(
        start: int, 
        end: int, 
        z3_solver: Z3Solver, 
        generator: Generator,
        inference_timeout: int,
        results_path: io.TextIOWrapper
):
    result_file = get_result_file(results_path)
    times = []
    for i in range(start, end):
        graph_file_path = os.path.join(config.benchmarks_graph_path, f'{i}.c.json')
        smt_file_path = os.path.join(config.benchmarks_smt_path, f'{i}.c.smt')
        code_file_path = os.path.join(config.benchmarks_code_path, f'{i}.c')
        sample_result_file_path = os.path.join(results_path, f'{i}.txt')

        z3_inv_smt_solver = InvSMTSolver(z3_solver, smt_file_path)
        runner = Runner(z3_inv_smt_solver, generator, code_file_path, sample_result_file_path, inference_timeout=inference_timeout)

        solution = runner.run()
        print(f"Solution for benchmark {i}: {solution}")

    result_file.close()

    print(times)

def main():
    parser = argparse.ArgumentParser(description="Run benchmarks")

    chat_gpt_models = [model.value for model in list(ChatGPTModel)]
    llama_models = [model.value for model in list(LlamaModel)]

    parser.add_argument("--llm-model", type=str, default="gpt-4o", help="LLM model to use", choices=chat_gpt_models+llama_models)
    parser.add_argument("--benchmark-range", type=valid_range, default="228-229", help="Range of benchmarks to run")
    parser.add_argument("--smt-timeout", type=int, default=50, help="Timeout for SMT check")
    parser.add_argument("--inference-timeout", type=int, default=600, help="Timeout for LLM inference")
    parser.add_argument("--results-path", type=str, default="results/test", help="Output directory for results")
    
    args = parser.parse_args()
    benchmark_range = [int(x) for x in args.benchmark_range.split("-")]

    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

    if args.llm_model in chat_gpt_models:
        if OPENAI_API_KEY is None:
            raise ValueError("OPENAI_API_KEY environment variable must be set")
        model = ChatGPTModel(args.llm_model)
        llm = ChatGPT(OPENAI_API_KEY, model)
    if args.llm_model in llama_models:
        model = LlamaModel(args.llm_model)
        llm = Llama(model)
    z3_solver = Z3Solver(args.smt_timeout)
    generator = Generator(llm, z3_solver)
    run_experiment(benchmark_range[0], benchmark_range[1], z3_solver, generator, args.inference_timeout, args.results_path)

if __name__ == "__main__":
    main()
