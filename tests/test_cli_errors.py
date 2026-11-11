import json
import pytest
import sys

import flamelink.cli as cli
from flamelink.report import build_report


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


def test_report_missing_file_exits_nonzero(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(sys, "argv", ["flamelink", "report", str(tmp_path / "missing.json")])

    with pytest.raises(SystemExit) as e:
        cli.main()
    assert e.value.code == 1
    assert "Cannot read" in capsys.readouterr().out


def test_report_invalid_report_exits_nonzero(monkeypatch, capsys, tmp_path):
    path = tmp_path / "report.json"
    path.write_text("{}")
    monkeypatch.setattr(sys, "argv", ["flamelink", "report", str(path)])

    with pytest.raises(SystemExit) as e:
        cli.main()
    assert e.value.code == 1
    assert "not a valid flamelink report" in capsys.readouterr().out


def test_report_valid_file_renders_once(monkeypatch, capsys, tmp_path):
    path = tmp_path / "report.json"
    path.write_text(json.dumps(build_report("http://localhost:8000/fib", 10, [10.0, 20.0, 30.0])))
    monkeypatch.setattr(sys, "argv", ["flamelink", "report", str(path)])

    cli.main()  # Should return normally, no SystemExit
    out = capsys.readouterr().out
    assert out.count("Report for http://localhost:8000/fib") == 1
    assert "No profiling data (load-only run)" in out
