import re
import shutil
import subprocess

_PERM_DENIED_RE = re.compile(
    r"EPERM|EACCES|permission denied|Operation not permitted|Permission denied",
    re.IGNORECASE
)
_NON_PYTHON_RE = re.compile(
    r"failed to find python",
    re.IGNORECASE
)


class ProfilerError(Exception):
    pass

def is_permission_denied(result_stderr: str) -> bool:
    return bool(_PERM_DENIED_RE.search(result_stderr))

def is_non_python_process(result_stderr: str) -> bool:
    return bool(_NON_PYTHON_RE.search(result_stderr))

def record(pid: int, duration: int, output_path: str) -> str:
    py_spy_path = shutil.which("py-spy")
    if py_spy_path is None:
        raise ProfilerError(
            "py-spy is not installed or not found in PATH. "
            "Please install py-spy and ensure it is available in your PATH."
        )
    
    cmd = [
        "sudo", py_spy_path, "record",
        "--output", output_path,
        "--pid", str(pid),
        "--duration", str(duration),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=duration + 10
        )
    except subprocess.TimeoutExpired:
        raise ProfilerError(
            f"Profiling timed out after {duration + 10} seconds. "
            f"This may be because sudo is waiting for a password with no tty available."
        )
    
    if result.returncode != 0:
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
        raise ProfilerError(f"Error occurred while profiling: {result.stderr}")

    return output_path
