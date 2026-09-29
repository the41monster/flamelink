import pytest
import sys

import flamelink.cli as cli


def test_profile_python_failure_exits_nonzero(monkeypatch, capsys):
    def fake_record_pyspy(pid, duration, output_path):
        raise cli.ProfilerError("boom")
    monkeypatch.setattr(cli, "record_pyspy", fake_record_pyspy)
    monkeypatch.setattr(sys, "argv", ["flamelink", "profile", "python", "--pid", "1234", "--duration", "1", "--out", "output.svg"])

    with pytest.raises(SystemExit) as e:
        cli.main()
    assert e.value.code == 1
    assert "Error during profiling: boom" in capsys.readouterr().out


def test_profile_node_failure_exits_nonzero(monkeypatch, capsys):
    def fake_record_clinicjs(command, duration, output_path, mode):
        raise cli.ProfilerError("boom")
    monkeypatch.setattr(cli, "record_clinicjs", fake_record_clinicjs)
    monkeypatch.setattr(sys, "argv", ["flamelink", "profile", "node","--out", "output.html", "--", "node", "app.js"])

    with pytest.raises(SystemExit) as e:
        cli.main()
    assert e.value.code == 1
    assert "Error during profiling: boom" in capsys.readouterr().out


def test_unexpected_error_exits_nonzero_python(monkeypatch, capsys):
    def fake_record_pyspy(pid, duration, output_path):
        raise Exception("boom")
    monkeypatch.setattr(cli, "record_pyspy", fake_record_pyspy)
    monkeypatch.setattr(sys, "argv", ["flamelink", "profile", "python", "--pid", "1234", "--duration", "1", "--out", "output.svg"])

    with pytest.raises(SystemExit) as e:
        cli.main()
    assert e.value.code == 1
    assert "Unexpected error during profiling: boom" in capsys.readouterr().out


def test_unexpected_error_exits_nonzero_node(monkeypatch, capsys):
    def fake_record_clinicjs(command, duration, output_path, mode):
        raise Exception("boom")
    monkeypatch.setattr(cli, "record_clinicjs", fake_record_clinicjs)
    monkeypatch.setattr(sys, "argv", ["flamelink", "profile", "node","--out", "output.html", "--", "node", "app.js"])

    with pytest.raises(SystemExit) as e:
        cli.main()
    assert e.value.code == 1
    assert "Unexpected error during profiling: boom" in capsys.readouterr().out
