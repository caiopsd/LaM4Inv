import tempfile
import os

from bmc.bmc import BMC
from utils.utils import run_command_with_timeout

class ESBMC(BMC):
    def __init__(self, bin_path: str, timeout: float, max_k_step: int = None):
        self.bin_path = bin_path
        self.timeout = timeout
        self.max_k_step = max_k_step
        pass

    def verify(self, code: str) -> bool:
        tmp_dir = tempfile.mkdtemp()
        tmp_file = os.path.join(tmp_dir, "main.c")
        with open(tmp_file, "w") as f:
            f.write(code)
        
        cmd = [self.bin_path, tmp_file, '--floatbv', '--k-induction']
        if self.max_k_step:
            cmd.extend(['--max-k-step', str(self.max_k_step)])
        run_command_with_timeout(cmd, self.timeout)