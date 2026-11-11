import json
import pytest
import sys

import flamelink.cli as cli
from flamelink.display import DEFAULT_TOP
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
    assert "Cannot read" in capsys.readouterr().err


def test_report_invalid_report_exits_nonzero(monkeypatch, capsys, tmp_path):
    path = tmp_path / "report.json"
    path.write_text("{}")
    monkeypatch.setattr(sys, "argv", ["flamelink", "report", str(path)])

    with pytest.raises(SystemExit) as e:
        cli.main()
    assert e.value.code == 1
    assert "not a valid flamelink report" in capsys.readouterr().err


def test_report_valid_file_renders_once(monkeypatch, capsys, tmp_path):
    path = tmp_path / "report.json"
    path.write_text(json.dumps(build_report("http://localhost:8000/fib", 10, [10.0, 20.0, 30.0])))
    monkeypatch.setattr(sys, "argv", ["flamelink", "report", str(path)])

    cli.main()  # No --format, so the table is the default. Should return normally, no SystemExit
    captured = capsys.readouterr()
    assert captured.out.count("Report for http://localhost:8000/fib") == 1
    assert "No profiling data (load-only run)" in captured.out
    assert captured.err == ""


def test_report_json_format_prints_exact_report(monkeypatch, capsys, tmp_path):
    # More rows than the table shows, so equality also proves JSON mode has no top-N limit.
    # "[eval]" checks that brackets aren't read as Rich markup.
    total = DEFAULT_TOP + 5
    hotspots = [
        {"fn": f"fn_{i:02d}", "file": "app.py", "line": i + 1, "self_pct": float(total - i), "total_pct": float(total - i)}
        for i in range(total)
    ]
    hotspots[0]["fn"] = "[eval]"
    report = build_report("http://localhost:8000/fib", 10, [10.0, 20.0, 30.0], sampler="clinic", hotspots=hotspots)
    path = tmp_path / "report.json"
    path.write_text(json.dumps(report))
    monkeypatch.setattr(sys, "argv", ["flamelink", "report", str(path), "--format", "json"])

    cli.main()
    captured = capsys.readouterr()
    assert json.loads(captured.out) == report  # Fails if anything besides the JSON reaches stdout
    assert captured.err == ""


def test_report_error_goes_to_stderr_only(monkeypatch, capsys, tmp_path):
    # A pipe only carries stdout, so `flamelink report ... --format json | jq` must get nothing on error
    monkeypatch.setattr(sys, "argv", ["flamelink", "report", str(tmp_path / "missing.json"), "--format", "json"])

    with pytest.raises(SystemExit) as e:
        cli.main()
    assert e.value.code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Cannot read" in captured.err


def test_report_rejects_unknown_format(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(sys, "argv", ["flamelink", "report", str(tmp_path / "report.json"), "--format", "xml"])

    with pytest.raises(SystemExit) as e:
        cli.main()
    assert e.value.code == 2  # argparse's exit code for usage errors
    assert "invalid choice" in capsys.readouterr().err
