import os
import signal
import shutil
import subprocess
import tempfile
import glob
import re

from flamelink.profilers.pyspy import ProfilerError


def record(command, duration, output_path, mode="flame"):
    clinicjs_path = shutil.which("clinic")
    if clinicjs_path is None:
        raise ProfilerError(
            "clinic.js is not installed or not found in PATH. "
            "Please install clinic.js and ensure it is available in your PATH."
        )

    if mode == "doctor":
        stale = glob.glob(os.path.join(os.getcwd(), "node_trace.*.log"))
        if len(stale) > 0:
            raise ProfilerError(
                f"Found stale node_trace.*.log files: {', '.join(stale)}. "
                "Please remove them before running the profiler."
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
            try:
                os.killpg(proc.pid, signal.SIGINT)
            except ProcessLookupError:
                pass
            try:
                stdout, stderr = proc.communicate(timeout=30)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                killed = True
                stdout, stderr = proc.communicate()

        match = re.search(r"Target subprocess error, code: (\d+)", stdout + stderr)
        if match and match.group(1) != "0":
            killed = False
            raise ProfilerError(
                f"Target subprocess exited early with a code: {match.group(1)}.\n{stderr}" 
            )
        
        if os.path.exists(os.path.join(tmpdir, f"flamelink.clinic-{mode}.html")):
            shutil.move(os.path.join(tmpdir, f"flamelink.clinic-{mode}.html"), output_path)
            with open(output_path, 'r', encoding='utf-8') as f:
                if not f.read().strip().endswith("-->"):
                    raise ProfilerError(
                        f"Clinic.js report at {output_path} appears to be incomplete (truncated write?). "
                        f"killed: {killed}"
                    )
        else:
            raise ProfilerError(
                f"Failed to generate clinic.js report. "
                f"stdout: {stdout}, stderr: {stderr}, killed: {killed}"
            )
  
    return output_path
