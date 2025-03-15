import signal

class TimeoutException(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutException("Function execution timed out")

def run_with_timeout(func, args=(), kwargs={}, timeout=5):
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(timeout)

    result = func(*args, **kwargs)
    signal.alarm(0)
    return result
