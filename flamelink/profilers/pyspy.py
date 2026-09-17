import subprocess


class ProfilerError(Exception):
    pass

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

    if result.returncode != 0:
        raise ProfilerError(f"Error occurred while profiling: {result.stderr}")

    return output_path
