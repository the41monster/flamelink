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

    with tempfile.TemporaryDirectory(prefix=".flamelink_clinic-", dir=os.getcwd()) as tmpdir:
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

        killed = False
        stdout = stderr = ""
        try:
            stdout, stderr = proc.communicate(timeout=duration)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGINT)
            try:
                stdout, stderr = proc.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                killed = True
                stdout, stderr = proc.communicate()

        if os.path.exists(os.path.join(tmpdir, f"flamelink.clinic-{mode}.html")):
            shutil.move(os.path.join(tmpdir, f"flamelink.clinic-{mode}.html"), output_path)
        else:
            raise ProfilerError(
                f"Failed to generate clinic.js report. "
                f"stdout: {stdout}, stderr: {stderr}, killed: {killed}"
            )
        return output_path
