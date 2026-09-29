import os
import signal
import pytest
import shutil
import subprocess

from flamelink.profilers.clinicjs import record
from flamelink.profilers.errors import ProfilerError


VALID_HTML = '<html></html>\n<!-- {"tool":"flame","toolVersion":"13.0.0","hash":"abc123"} -->\n'


def test_clinic_not_installed(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: None)
    with pytest.raises(ProfilerError, match="clinic"):
        record(command=["node", "app.js"], duration=1, output_path="output")


def test_doctor_stale_trace_logs(monkeypatch, tmp_path):
    monkeypatch.setattr(shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.chdir(tmp_path)
    trace_file = tmp_path / "node_trace.1.log"
    trace_file.touch()

    with pytest.raises(ProfilerError, match="stale"):
        record(command=["node", "app.js"], duration=1, output_path="output", mode="doctor")

    assert trace_file.exists()


def make_fake_popen(stdout="", stderr="", html=None, timeouts=0):
    class FakePopen:
        def __init__(self, cmd, **kwargs):
            self.calls = 0
            self.pid = 999999
            if html is not None:
                dest = cmd[cmd.index("--dest") + 1]
                mode = cmd[1]
                with open(os.path.join(dest, f"flamelink.clinic-{mode}.html"), "w") as f:
                    f.write(html)

        def communicate(self, timeout=None):
            self.calls += 1
            if self.calls <= timeouts and timeout is not None:
                raise subprocess.TimeoutExpired(cmd="clinic", timeout=timeout)
            return stdout, stderr
    return FakePopen


def test_flame_target_exits_early(monkeypatch, tmp_path):
    monkeypatch.setattr(shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(subprocess, "Popen", make_fake_popen(stderr="Target subprocess error, code: 1"))
    monkeypatch.setattr(os, "killpg", lambda pid, sig: None)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ProfilerError, match="exited early"):
        record(command=["node", "app.js"], duration=1, output_path="output")


def test_doctor_target_exits_early(monkeypatch, tmp_path):
    monkeypatch.setattr(shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(subprocess, "Popen", make_fake_popen(stderr="process exited with exit code 1"))
    monkeypatch.setattr(os, "killpg", lambda pid, sig: None)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ProfilerError, match="exited early"):
        record(command=["node", "app.js"], duration=1, output_path="output", mode="doctor")


def test_no_html_produced(monkeypatch, tmp_path):
    monkeypatch.setattr(shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(subprocess, "Popen", make_fake_popen(html=None))
    monkeypatch.setattr(os, "killpg", lambda pid, sig: None)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ProfilerError, match="Failed to generate"):
        record(command=["node", "app.js"], duration=1, output_path="output")


def test_truncated_report_is_removed(monkeypatch, tmp_path):
    monkeypatch.setattr(shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(subprocess, "Popen", make_fake_popen(html="<html><head><style>"))
    monkeypatch.setattr(os, "killpg", lambda pid, sig: None)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ProfilerError, match="incomplete"):
        record(command=["node", "app.js"], duration=1, output_path="output")
    
    assert not os.path.exists(tmp_path / "output"), "Truncated report file should be removed"


def test_valid_report_succeeds(monkeypatch, tmp_path):
    monkeypatch.setattr(shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(subprocess, "Popen", make_fake_popen(html=VALID_HTML))
    monkeypatch.setattr(os, "killpg", lambda pid, sig: None)
    monkeypatch.chdir(tmp_path)

    output_path = tmp_path / "output"
    result = record(command=["node", "app.js"], duration=1, output_path=output_path)

    assert result == output_path, "record() should return the output path"
    assert output_path.read_text() == VALID_HTML, "Report file content should match expected HTML"


def test_target_exit_code_zero_is_not_an_error(monkeypatch, tmp_path):
    monkeypatch.setattr(shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(subprocess, "Popen", make_fake_popen(stderr="Target subprocess error, code: 0", html=VALID_HTML))
    monkeypatch.setattr(os, "killpg", lambda pid, sig: None)
    monkeypatch.chdir(tmp_path)

    output_path = tmp_path / "output"
    record(command=["node", "app.js"], duration=1, output_path=output_path)

    assert os.path.exists(output_path), "Report file should be created even if target exit code is 0"


def test_timeout_sends_sigint_then_succeeds(monkeypatch, tmp_path):
    monkeypatch.setattr(shutil, "which", lambda name: f"/usr/bin/{name}")
    signals = []
    monkeypatch.setattr(os, "killpg", lambda pid, sig: signals.append((pid, sig)))
    monkeypatch.setattr(subprocess, "Popen", make_fake_popen(html=VALID_HTML, timeouts=1))
    monkeypatch.chdir(tmp_path)

    output_path = tmp_path / "output"
    result = record(command=["node", "app.js"], duration=1, output_path=output_path)

    assert result == output_path, "record() should return the output path"
    assert signals == [(999999, signal.SIGINT)], "SIGINT should be sent to the process group on timeout"


def test_timeout_escalates_to_sigkill(monkeypatch, tmp_path):
    monkeypatch.setattr(shutil, "which", lambda name: f"/usr/bin/{name}")
    signals = []
    monkeypatch.setattr(os, "killpg", lambda pid, sig: signals.append((pid, sig)))
    monkeypatch.setattr(subprocess, "Popen", make_fake_popen(html="<html><head>", timeouts=2))
    monkeypatch.chdir(tmp_path)

    output_path = tmp_path / "output"
    with pytest.raises(ProfilerError, match="killed: True"):
        record(command=["node", "app.js"], duration=1, output_path=output_path)
    
    assert signals == [(999999, signal.SIGINT), (999999, signal.SIGKILL)], "SIGINT and SIGKILL should be sent on repeated timeouts"
