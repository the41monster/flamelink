import subprocess
import re


class ProfilerError(Exception):
    pass

def is_permission_denied(result_stderr: str) -> bool:
    _PERM_DENIED_RE = re.compile(
        r"EPERM|EACCES|permission denied|Operation not permitted|Permission denied",
        re.IGNORECASE
    )
    return bool(_PERM_DENIED_RE.search(result_stderr))

def is_non_python_process(result_stderr: str) -> bool:
    _NON_PYTHON_RE = re.compile(
        r"failed to find python",
        re.IGNORECASE
    )
    return bool(_NON_PYTHON_RE.search(result_stderr))

def record(pid: int, duration: int, output_path: str) -> str:
    cmd = [
        "sudo", ".venv/bin/py-spy", "record",
        "--output", output_path,
        "--pid", str(pid),
        "--duration", str(duration),
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True
    )
    if result.stderr and is_permission_denied(result.stderr):
        raise ProfilerError(
            f"Permission denied error occurred while profiling.\n"
            f"If you are running this in a container, make sure to run the container with the --cap-add=SYS_PTRACE flag (or a seccomp profile that allows ptrace).\n"
            f"Original error: {result.stderr}"
        )
    if result.stderr and is_non_python_process(result.stderr):
        raise ProfilerError(
            f"Non-Python process error occurred while profiling.\n"
            f"Make sure the process with PID {pid} is a Python process.\n"
            f"Original error: {result.stderr}"
        )
    if result.returncode != 0:
        raise ProfilerError(f"Error occurred while profiling: {result.stderr}")

    return output_path
