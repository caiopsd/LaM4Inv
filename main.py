import argparse
import os

from runner import Runner
from config import config
from inv_smt_solver.z3_inv_smt_solver import Z3InvSMTSolver

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

def get_result_file():
    os.makedirs(config.result_path, exist_ok=True)
    return open(os.path.join(config.result_path, 'result.txt'), "a")

def run_experiment(start: int, end: int):
    result_file = get_result_file()
    times = []
    for i in range(start, end):
        graph_file_path = os.path.join(config.benchmarks_graph_path, f'{i}.c.json')
        smt_file_path = os.path.join(config.benchmarks_smt_path, f'{i}.c.smt')
        c_file_path = os.path.join(config.benchmarks_c_path, f'{i}.c')
        sample_result_file_path = os.path.join(config.result_path, f'{i}.txt')

        z3_inv_smt_solver = Z3InvSMTSolver(smt_file_path, config.smt_check_timeout)
        runner = Runner(z3_inv_smt_solver)

        time, answer, gpt_answers, iterations = runner.run(graph_file_path, smt_file_path, c_file_path, sample_result_file_path) 

        times.append(time)

        result_file.write(f'{c_file_path}\n')
        for gpt_answer in gpt_answers:
            result_file.write(f'{gpt_answer}\n')
        result_file.write(f'{time}\t{answer}\t{iterations}\n')
        result_file.write('\n')
        result_file.flush()

    result_file.close()

    print(times)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--range", type=valid_range, default="228-229")
    args = parser.parse_args()
    range = [int(x) for x in args.range.split("-")]

    run_experiment(range[0], range[1])

if __name__ == "__main__":
    main()
