import subprocess
import sys
import time


class ManagedProcess:
    def __init__(self, name, process):
        self.name = name
        self.process = process

    def stop(self, timeout=5):
        if self.process.poll() is not None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=timeout)

    def stderr_tail(self, limit=2000):
        if not self.process.stderr or self.process.poll() is None:
            return ""
        return self.process.stderr.read()[-limit:]


def start_python_module(name, module, *args, python_executable=None, env=None):
    command = [python_executable or sys.executable, "-m", module, *args]
    process = subprocess.Popen(
        command,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return ManagedProcess(name, process)


def stop_all(processes):
    for process in reversed(processes):
        process.stop()


def wait_for_process_exit(processes, seconds=0.5):
    deadline = time.time() + seconds
    while time.time() < deadline:
        failed = [
            process
            for process in processes
            if process.process.poll() not in (None, 0)
        ]
        if failed:
            return failed
        time.sleep(0.05)
    return []
