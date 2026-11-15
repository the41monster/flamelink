import os
import signal
import pytest
import shutil
import subprocess
from pathlib import Path

from flamelink.profilers.clinicjs import POLL_INTERVAL_S, record
from flamelink.profilers.errors import ProfilerError


VALID_HTML = '<html></html>\n<!-- {"tool":"flame","toolVersion":"13.0.0","hash":"abc123"} -->\n'


def make_fake_popen(stdout="", stderr="", html=None, timeouts=0, trace_log=False):
    class FakePopen:
        def __init__(self, cmd, **kwargs):
            self.calls = 0
            self.pid = 999999
            if trace_log:
                trace_file = Path(os.path.join(os.getcwd(), "node_trace.1.log"))
                trace_file.touch()
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


def test_doctor_cleans_trace_log_on_success(monkeypatch, tmp_path):
    monkeypatch.setattr(shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(subprocess, "Popen", make_fake_popen(html=VALID_HTML, trace_log=True))
    monkeypatch.setattr(os, "killpg", lambda pid, sig: None)
    monkeypatch.chdir(tmp_path)

    output_path = tmp_path / "output"
    result = record(command=["node", "app.js"], duration=1, output_path=output_path, mode="doctor")

    trace_file = tmp_path / "node_trace.1.log"

    assert result == output_path, "record() should return the output path"
    assert not trace_file.exists(), "Trace log should be cleaned up after successful doctor run"


def test_doctor_cleans_trace_log_on_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(subprocess, "Popen", make_fake_popen(stderr="process exited with exit code 1", trace_log=True))
    monkeypatch.setattr(os, "killpg", lambda pid, sig: None)
    monkeypatch.chdir(tmp_path)

    output_path = tmp_path / "output"
    with pytest.raises(ProfilerError, match="exited early"):
        record(command=["node", "app.js"], duration=1, output_path=output_path, mode="doctor")

    trace_file = tmp_path / "node_trace.1.log"

    assert not trace_file.exists(), "Trace log should be cleaned up even after failed doctor run"


# --- stop_event mode ---

class FakeEvent:
    """Reports set from its `set_on`-th is_set() call on, so a test controls exactly when load "ends"."""
    def __init__(self, set_on):
        self.checks = 0
        self.set_on = set_on

    def is_set(self):
        self.checks += 1
        return self.checks >= self.set_on


def run_with_event(monkeypatch, tmp_path, event, **popen_kwargs):
    """Run record() in event mode with a FakePopen. Returns (sent signals, communicate timeouts)."""
    signals = []
    timeouts_seen = []
    FakePopen = make_fake_popen(**popen_kwargs)
    original_communicate = FakePopen.communicate

    def recording_communicate(self, timeout=None):
        timeouts_seen.append(timeout)
        return original_communicate(self, timeout)

    monkeypatch.setattr(FakePopen, "communicate", recording_communicate)
    monkeypatch.setattr(shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(subprocess, "Popen", FakePopen)
    monkeypatch.setattr(os, "killpg", lambda pid, sig: signals.append(sig))
    monkeypatch.chdir(tmp_path)

    record(command=["node", "app.js"], duration=1, output_path=str(tmp_path / "output.html"), stop_event=event)
    return signals, timeouts_seen


def test_event_already_set_sends_sigint_once(monkeypatch, tmp_path):
    # First poll times out, the event is already set, so clinic gets SIGINT and exits during the grace period
    signals, timeouts_seen = run_with_event(monkeypatch, tmp_path, FakeEvent(set_on=1), html=VALID_HTML, timeouts=1)

    assert signals == [signal.SIGINT]
    assert timeouts_seen == [POLL_INTERVAL_S, 30]
    assert (tmp_path / "output.html").exists()


def test_event_set_after_several_polls(monkeypatch, tmp_path):
    # Load "ends" on the 3rd check: 3 polls, then SIGINT, then the grace-period communicate returns
    signals, timeouts_seen = run_with_event(monkeypatch, tmp_path, FakeEvent(set_on=3), html=VALID_HTML, timeouts=3)

    assert signals == [signal.SIGINT]
    assert timeouts_seen == [POLL_INTERVAL_S] * 3 + [30]
    assert (tmp_path / "output.html").exists()


def test_event_mode_clinic_exits_on_its_own(monkeypatch, tmp_path):
    # The event is never set, but clinic finishes after 3 polls: no signal is sent
    signals, timeouts_seen = run_with_event(monkeypatch, tmp_path, FakeEvent(set_on=99), html=VALID_HTML, timeouts=3)

    assert signals == []
    assert timeouts_seen == [POLL_INTERVAL_S] * 4
    assert (tmp_path / "output.html").exists()


def test_event_mode_target_crash_is_noticed_while_polling(monkeypatch, tmp_path):
    # The target dies before the load ends: reported as "exited early", without waiting for the event
    with pytest.raises(ProfilerError, match="exited early"):
        run_with_event(monkeypatch, tmp_path, FakeEvent(set_on=99),
                       stderr="Target subprocess error, code: 1", timeouts=2)


def test_event_mode_escalates_to_sigkill(monkeypatch, tmp_path):
    # Event set, and clinic also ignores SIGINT for the whole grace period: same escalation as duration mode
    signals, timeouts_seen = run_with_event(monkeypatch, tmp_path, FakeEvent(set_on=1), html=VALID_HTML, timeouts=2)

    assert signals == [signal.SIGINT, signal.SIGKILL]
    assert timeouts_seen == [POLL_INTERVAL_S, 30, None]
