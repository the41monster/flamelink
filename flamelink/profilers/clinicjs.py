import os
import signal
import shutil
import subprocess
import tempfile

from flamelink.profilers.pyspy import ProfilerError


def record(command, duration, output_path, mode="flame"):
    clinicjs_path = shutil.which("clinic")
    if clinicjs_path is None:
        raise ProfilerError(
            "clinic.js is not installed or not found in PATH. "
            "Please install clinic.js and ensure it is available in your PATH."
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        cmd = [
            clinicjs_path, mode,
            "--open=false",
            "--dest", tmpdir,
            "--name", "flamelink",
            "--", *command
        ]

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True
        )

        try:
            proc.communicate(timeout=duration)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGINT)
            try:
                proc.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.communicate()

        shutil.move(os.path.join(tmpdir, "flamelink.clinic-flame.html"), output_path)

        return output_path
