import pytest
import shutil
import subprocess

from flamelink.profilers.pyspy import record
from flamelink.profilers.errors import ProfilerError


def test_pyspy_not_installed(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: None)
    with pytest.raises(ProfilerError, match="py-spy"):
        record(pid=1234, duration=1, output_path="output.svg")


def test_sudo_not_installed(monkeypatch):
    def mock_which(name):
        if name == "py-spy":
            return "/usr/bin/py-spy"
        return None

    monkeypatch.setattr(shutil, "which", mock_which)
    with pytest.raises(ProfilerError, match="sudo"):
        record(pid=1234, duration=1, output_path="output.svg")


def test_timeout(monkeypatch):
    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="py-spy", timeout=11)

    monkeypatch.setattr(shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(ProfilerError, match="Profiling timed out"):
        record(pid=1234, duration=1, output_path="output.svg")


def make_fake_run(returncode=1, stderr="Permission denied"):
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args=args, returncode=returncode, stdout="", stderr=stderr)
    return fake_run


def test_non_python_process(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(subprocess, "run", make_fake_run(stderr="Error: Failed to find python version from target process"))

    with pytest.raises(ProfilerError, match="Non-Python"):
        record(pid=1234, duration=1, output_path="output.svg")


def test_pid_not_found(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(subprocess, "run", make_fake_run(stderr="Error: Failed to get process executable name. Check that the process is running."))

    with pytest.raises(ProfilerError, match="Error occurred while profiling"):
        record(pid=1234, duration=1, output_path="output.svg")


def test_permission_denied(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: f"/usr/bin/{name}")
    # Assumed py-spy output, never captured from a real run
    monkeypatch.setattr(subprocess, "run", make_fake_run(stderr="Error: EPERM (os error 1)"))

    with pytest.raises(ProfilerError, match="SYS_PTRACE"):
        record(pid=1234, duration=1, output_path="output.svg")


def test_success_with_permission_text_in_stderr(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(subprocess, "run", make_fake_run(returncode=0, stderr="permission denied"))

    output_path = record(pid=1234, duration=1, output_path="output.svg")
    assert output_path == "output.svg"
