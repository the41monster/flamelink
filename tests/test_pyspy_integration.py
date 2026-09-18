import os
import subprocess
import time
import urllib.error
import urllib.request

import asyncio
import pytest

from flamelink.load import generate_load
from flamelink.profilers.pyspy import record

PORT = int(os.environ.get("TEST_FASTAPI_PORT", 47821))
URL = f"http://localhost:{PORT}/cpu/?iterations=1000000"

@pytest.fixture
def fastapi_server():
    proc = subprocess.Popen(
        ["uvicorn", "demos.python.server:app",
         "--host", "localhost",
         "--port", str(PORT),
         "--workers", "1"
        ]
    )
    deadline = time.time() + 10  # 10 seconds from now
    while True:
        if proc.poll() is not None:
            raise RuntimeError(
                f"uvicorn exited with {proc.returncode} "
                f"(port {PORT} may already be in use)"
            )
        try:
            urllib.request.urlopen(URL, timeout=0.5).close()
            break
        except urllib.error.HTTPError:
            break  # server is up, but endpoint returned an error
        except (urllib.error.URLError, OSError):
            if time.monotonic() > deadline:
                proc.kill()
                raise RuntimeError(
                    f"server not ready after 10 seconds on {PORT}"
                )
            time.sleep(0.05)
    try:
        yield proc
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


@pytest.mark.asyncio
async def test_pyspy_captures_load(fastapi_server, tmp_path):
    pid = fastapi_server.pid
    url = URL
    rps = 5
    duration = 5
    output_path = tmp_path / "profile.svg"
    record_task = asyncio.to_thread(record, pid, duration, output_path)
    load_task = asyncio.create_task(generate_load(url, rps, duration))
    await asyncio.gather(record_task, load_task)
    assert output_path.exists(), "Profile output file was not created"
    assert output_path.stat().st_size > 0, "Profile output file is empty"
    assert "ERROR: No valid input files found" not in output_path.read_text(), "Profile output file is invalid"
