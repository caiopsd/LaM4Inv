import signal
import subprocess

def timeout_handler(signum, frame):
    raise TimeoutError("Function execution timed out")

def run_with_timeout(func, args=(), kwargs={}, timeout=5):
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(timeout)

    result = func(*args, **kwargs)
    signal.alarm(0)
    return result

def run_command_with_timeout(command: str, timeout: float):
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
        return stdout, stderr
    except subprocess.TimeoutExpired:
        process.kill()
        raise TimeoutError(f"Command {command} timed out")