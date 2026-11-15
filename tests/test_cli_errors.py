import json
import pytest
import sys

import flamelink.cli as cli
from flamelink.display import DEFAULT_TOP
from flamelink.report import build_report, load_report


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


# 10 samples: all -> main -> {fib -> fib (recursive), idle}.
# Copied from test_reporters.py so test files don't import each other.
PYSPY_SVG = """\
<svg xmlns="http://www.w3.org/2000/svg" xmlns:fg="http://github.com/jonhoo/inferno">
    <g><title>all (10 samples, 100%)</title><rect x="0%" y="0" width="100%" fg:x="0" fg:w="10"/></g>
    <g><title>main (app.py:1) (10 samples, 100.00%)</title><rect x="0%" y="16" width="100%" fg:x="0" fg:w="10"/></g>
    <g><title>fib (app.py:5) (8 samples, 80.00%)</title><rect x="0%" y="32" width="80%" fg:x="0" fg:w="8"/></g>
    <g><title>fib (app.py:5) (6 samples, 60.00%)</title><rect x="0%" y="48" width="60%" fg:x="0" fg:w="6"/></g>
    <g><title>idle (app.py:9) (2 samples, 20.00%)</title><rect x="80%" y="32" width="20%" fg:x="8" fg:w="2"/></g>
</svg>
"""

PYSPY_EXPECTED = [
    {"fn": "fib",  "file": "app.py", "line": 5, "self_pct": 80.0, "total_pct": 80.0},
    {"fn": "idle", "file": "app.py", "line": 9, "self_pct": 20.0, "total_pct": 20.0},
    {"fn": "main", "file": "app.py", "line": 1, "self_pct": 0.0,  "total_pct": 100.0},
]

URL = "http://localhost:8000/fib/?n=25"


def test_profile_python_report_without_url_is_rejected(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(sys, "argv", ["flamelink", "profile", "python", "--pid", "1234",
                                      "--out", str(tmp_path / "p.svg"), "--report", str(tmp_path / "r.json")])

    with pytest.raises(SystemExit) as e:
        cli.main()
    assert e.value.code == 2  # argparse's exit code for usage errors
    assert "--report requires --url" in capsys.readouterr().err


def test_profile_python_url_without_report_is_rejected(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(sys, "argv", ["flamelink", "profile", "python", "--pid", "1234",
                                      "--out", str(tmp_path / "p.svg"), "--url", URL])

    with pytest.raises(SystemExit) as e:
        cli.main()
    assert e.value.code == 2
    assert "--url requires --report" in capsys.readouterr().err


def test_profile_python_with_url_writes_combined_report(monkeypatch, tmp_path):
    # Fake both sides so this runs without sudo, py-spy or a server
    calls = {}

    def fake_record_pyspy(pid, duration, output_path):
        calls["record"] = (pid, duration, output_path)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(PYSPY_SVG)

    async def fake_generate_load(url, rps, duration_s):
        calls["load"] = (url, rps, duration_s)
        return [10.0, 20.0, 30.0], {}

    monkeypatch.setattr(cli, "ensure_sudo", lambda: None)
    monkeypatch.setattr(cli, "record_pyspy", fake_record_pyspy)
    monkeypatch.setattr(cli, "generate_load", fake_generate_load)

    svg_path = tmp_path / "profile.svg"
    report_path = tmp_path / "report.json"
    monkeypatch.setattr(sys, "argv", ["flamelink", "profile", "python", "--pid", "1234",
                                      "--url", URL, "--rps", "7", "--duration", "3",
                                      "--out", str(svg_path), "--report", str(report_path)])

    cli.main()  # Should return normally, no SystemExit

    # Both ran, with the arguments from the command line, sharing one duration
    assert calls["record"] == (1234, 3, str(svg_path))
    assert calls["load"] == (URL, 7, 3)

    # The profile is still the SVG; the report went to its own file
    assert svg_path.read_text(encoding="utf-8") == PYSPY_SVG

    report = load_report(str(report_path))  # Raises ReportError if it doesn't validate
    assert report["target"] == URL
    assert report["duration_s"] == 3
    assert report["sampler"] == "py-spy"
    assert report["p50_ms"] == 20.0
    assert report["hotspots"] == PYSPY_EXPECTED


def test_profile_python_with_url_profiler_failure_exits_nonzero(monkeypatch, capsys, tmp_path):
    # If py-spy fails, gather re-raises its error: exit 1, and no half-made report is left behind
    def fake_record_pyspy(pid, duration, output_path):
        raise cli.ProfilerError("boom")

    async def fake_generate_load(url, rps, duration_s):
        return [10.0, 20.0, 30.0], {}

    monkeypatch.setattr(cli, "ensure_sudo", lambda: None)
    monkeypatch.setattr(cli, "record_pyspy", fake_record_pyspy)
    monkeypatch.setattr(cli, "generate_load", fake_generate_load)

    report_path = tmp_path / "report.json"
    monkeypatch.setattr(sys, "argv", ["flamelink", "profile", "python", "--pid", "1234", "--url", URL,
                                      "--out", str(tmp_path / "profile.svg"), "--report", str(report_path)])

    with pytest.raises(SystemExit) as e:
        cli.main()
    assert e.value.code == 1
    assert "Error during profiling: boom" in capsys.readouterr().out
    assert not report_path.exists()


def test_profile_python_with_url_asks_for_sudo_before_anything_starts(monkeypatch, tmp_path):
    # If sudo prompted inside the record thread, load would already be running and
    # latency and hotspots would cover different time windows
    order = []

    def fake_ensure_sudo():
        order.append("sudo")

    def fake_record_pyspy(pid, duration, output_path):
        order.append("record")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(PYSPY_SVG)

    async def fake_generate_load(url, rps, duration_s):
        order.append("load")
        return [10.0, 20.0, 30.0], {}

    monkeypatch.setattr(cli, "ensure_sudo", fake_ensure_sudo)
    monkeypatch.setattr(cli, "record_pyspy", fake_record_pyspy)
    monkeypatch.setattr(cli, "generate_load", fake_generate_load)
    monkeypatch.setattr(sys, "argv", ["flamelink", "profile", "python", "--pid", "1234", "--url", URL,
                                      "--out", str(tmp_path / "profile.svg"), "--report", str(tmp_path / "report.json")])

    cli.main()

    # record and load run concurrently, so only the first item has a fixed position
    assert order[0] == "sudo"
    assert order.count("sudo") == 1
    assert sorted(order[1:]) == ["load", "record"]


def test_profile_python_with_url_sudo_failure_starts_nothing(monkeypatch, capsys, tmp_path):
    order = []

    def fake_ensure_sudo():
        raise cli.ProfilerError("sudo authentication failed")

    def fake_record_pyspy(pid, duration, output_path):
        order.append("record")

    async def fake_generate_load(url, rps, duration_s):
        order.append("load")
        return [], {}

    monkeypatch.setattr(cli, "ensure_sudo", fake_ensure_sudo)
    monkeypatch.setattr(cli, "record_pyspy", fake_record_pyspy)
    monkeypatch.setattr(cli, "generate_load", fake_generate_load)

    report_path = tmp_path / "report.json"
    monkeypatch.setattr(sys, "argv", ["flamelink", "profile", "python", "--pid", "1234", "--url", URL,
                                      "--out", str(tmp_path / "profile.svg"), "--report", str(report_path)])

    with pytest.raises(SystemExit) as e:
        cli.main()
    assert e.value.code == 1
    assert "sudo authentication failed" in capsys.readouterr().out
    assert order == []  # No load sent, no profile recorded
    assert not report_path.exists()


def test_profile_python_with_url_unparseable_profile_exits_nonzero(monkeypatch, capsys, tmp_path):
    # An SVG without the "all" root frame: pyspy_hotspots can't get the sample count and raises ValueError
    svg_without_root = """\
<svg xmlns="http://www.w3.org/2000/svg" xmlns:fg="http://github.com/jonhoo/inferno">
    <g><title>main (app.py:1) (10 samples, 100.00%)</title><rect x="0%" y="0" width="100%" fg:x="0" fg:w="10"/></g>
</svg>
"""

    def fake_record_pyspy(pid, duration, output_path):
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(svg_without_root)

    async def fake_generate_load(url, rps, duration_s):
        return [10.0, 20.0, 30.0], {}

    monkeypatch.setattr(cli, "ensure_sudo", lambda: None)
    monkeypatch.setattr(cli, "record_pyspy", fake_record_pyspy)
    monkeypatch.setattr(cli, "generate_load", fake_generate_load)

    svg_path = tmp_path / "profile.svg"
    report_path = tmp_path / "report.json"
    monkeypatch.setattr(sys, "argv", ["flamelink", "profile", "python", "--pid", "1234", "--url", URL,
                                      "--out", str(svg_path), "--report", str(report_path)])

    with pytest.raises(SystemExit) as e:
        cli.main()
    assert e.value.code == 1
    out = capsys.readouterr().out
    assert "hotspots could not be extracted" in out
    assert "Unexpected error" not in out
    assert svg_path.read_text(encoding="utf-8") == svg_without_root  # The profile is kept for a manual look
    assert not report_path.exists()


# 10 samples: root -> (anonymous) -> {fib -> fib (recursive), [SHARED_LIB] -> syscall}.
# Copied from test_reporters.py so test files don't import each other.
CLINIC_HTML = """\
<html><script>var data = {"merged":{
  "value": 10, "onStackTop": {"base": 0}, "children": [
    {"functionName": "(anonymous)", "fileName": "./server.js", "lineNumber": 7,
     "value": 10, "onStackTop": {"base": 0}, "children": [
      {"functionName": "fib", "fileName": "./utils.js", "lineNumber": 1,
       "value": 7, "onStackTop": {"base": 2}, "children": [
        {"functionName": "fib", "fileName": "./utils.js", "lineNumber": 1,
         "value": 5, "onStackTop": {"base": 5}, "children": []}
      ]},
      {"functionName": "[SHARED_LIB]", "fileName": "/usr/bin/node", "lineNumber": null,
       "value": 3, "onStackTop": {"base": 2}, "children": [
        {"functionName": "syscall", "fileName": null, "lineNumber": null,
         "value": 1, "onStackTop": {"base": 1}, "children": []}
      ]}
    ]}
  ]
}}</script></html>
"""

CLINIC_EXPECTED = [
    {"fn": "fib",  "file": "./utils.js", "line": 1, "self_pct": 70.0, "total_pct": 70.0},
    {"fn": "[SHARED_LIB]", "file": "/usr/bin/node", "line": None, "self_pct": 20.0, "total_pct": 30.0},
    {"fn": "syscall", "file": None, "line": None, "self_pct": 10.0, "total_pct": 10.0},
    {"fn": "(anonymous)", "file": "./server.js", "line": 7, "self_pct": 0.0, "total_pct": 100.0},
]

NODE_URL = "http://localhost:3000/fib/?n=25"


def test_profile_node_with_url_writes_combined_report(monkeypatch, tmp_path):
    # Fake clinic, the readiness check and the load, so this runs without node or a server
    calls = {}

    def fake_record_clinicjs(command, duration, output_path, mode, stop_event):
        calls["record"] = (command, output_path, mode)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(CLINIC_HTML)
        # Like the real event mode: keep "profiling" until the load is over
        calls["stopped"] = stop_event.wait(timeout=2)

    async def fake_wait_until_ready(url):
        calls["ready"] = url

    async def fake_generate_load(url, rps, duration_s):
        calls["load"] = (url, rps, duration_s)
        return [10.0, 20.0, 30.0], {}

    monkeypatch.setattr(cli, "record_clinicjs", fake_record_clinicjs)
    monkeypatch.setattr(cli, "wait_until_ready", fake_wait_until_ready)
    monkeypatch.setattr(cli, "generate_load", fake_generate_load)

    html_path = tmp_path / "flame.html"
    report_path = tmp_path / "report.json"
    monkeypatch.setattr(sys, "argv", ["flamelink", "profile", "node",
                                      "--url", NODE_URL, "--rps", "7", "--duration", "3",
                                      "--out", str(html_path), "--report", str(report_path),
                                      "--", "node", "server.js"])

    cli.main()  # Should return normally, no SystemExit

    assert calls["record"] == (["node", "server.js"], str(html_path), "flame")
    assert calls["ready"] == NODE_URL
    assert calls["load"] == (NODE_URL, 7, 3)
    assert calls["stopped"] is True  # clinic was told to stop when the load ended

    report = load_report(str(report_path))  # Raises ReportError if it doesn't validate
    assert report["target"] == NODE_URL
    assert report["duration_s"] == 3
    assert report["sampler"] == "clinic"
    assert report["p50_ms"] == 20.0
    assert report["hotspots"] == CLINIC_EXPECTED


def test_profile_node_report_without_url_is_rejected(monkeypatch, capsys, tmp_path):
    # The --url/--report pairing check is shared; this shows it now covers node too.
    # Clinic is faked so a broken check fails fast instead of spawning a real node process.
    started = []

    def fake_record_clinicjs(**kwargs):
        started.append(True)

    monkeypatch.setattr(cli, "record_clinicjs", fake_record_clinicjs)
    monkeypatch.setattr(sys, "argv", ["flamelink", "profile", "node",
                                      "--out", str(tmp_path / "flame.html"), "--report", str(tmp_path / "r.json"),
                                      "--", "node", "server.js"])

    with pytest.raises(SystemExit) as e:
        cli.main()
    assert e.value.code == 2
    assert "--report requires --url" in capsys.readouterr().err
    assert started == []


def test_profile_node_url_with_doctor_mode_is_rejected(monkeypatch, capsys, tmp_path):
    # Doctor's HTML has no flamegraph data, so the run would only fail at the parse step.
    # It must be rejected before clinic starts. Everything is faked so a broken check
    # fails fast instead of polling a real port.
    started = []

    def fake_record_clinicjs(**kwargs):
        started.append(True)

    async def fake_wait_until_ready(url):
        pass

    async def fake_generate_load(url, rps, duration_s):
        return [], {}

    monkeypatch.setattr(cli, "record_clinicjs", fake_record_clinicjs)
    monkeypatch.setattr(cli, "wait_until_ready", fake_wait_until_ready)
    monkeypatch.setattr(cli, "generate_load", fake_generate_load)
    monkeypatch.setattr(sys, "argv", ["flamelink", "profile", "node", "--mode", "doctor",
                                      "--url", NODE_URL, "--out", str(tmp_path / "doctor.html"),
                                      "--report", str(tmp_path / "r.json"),
                                      "--", "node", "server.js"])

    with pytest.raises(SystemExit) as e:
        cli.main()
    assert e.value.code == 2
    assert "--mode doctor" in capsys.readouterr().err
    assert started == []


def test_profile_node_with_url_clinic_failure_exits_nonzero(monkeypatch, capsys, tmp_path):
    # Clinic dies on startup: the server never comes up, and clinic's own error is what the user sees
    def fake_record_clinicjs(**kwargs):
        raise cli.ProfilerError("clinic exited early")

    async def fake_wait_until_ready(url):
        raise cli.ProfilerError("not ready")

    async def fake_generate_load(url, rps, duration_s):
        return [], {}

    monkeypatch.setattr(cli, "record_clinicjs", fake_record_clinicjs)
    monkeypatch.setattr(cli, "wait_until_ready", fake_wait_until_ready)
    monkeypatch.setattr(cli, "generate_load", fake_generate_load)

    report_path = tmp_path / "report.json"
    monkeypatch.setattr(sys, "argv", ["flamelink", "profile", "node", "--url", NODE_URL,
                                      "--out", str(tmp_path / "flame.html"), "--report", str(report_path),
                                      "--", "node", "server.js"])

    with pytest.raises(SystemExit) as e:
        cli.main()
    assert e.value.code == 1
    assert "Error during profiling: clinic exited early" in capsys.readouterr().out
    assert not report_path.exists()


def test_profile_python_zero_rps_is_rejected_before_sudo(monkeypatch, capsys, tmp_path):
    # A bad --rps must stop at parse time. Before, it was only caught inside the load
    # generator, after py-spy had started, so the user waited out the full --duration.
    # Everything is faked so a broken check fails fast instead of attaching py-spy.
    started = []

    def fake_ensure_sudo():
        started.append("sudo")

    def fake_record_pyspy(pid, duration, output_path):
        started.append("record")

    async def fake_generate_load(url, rps, duration_s):
        started.append("load")
        return [], {}

    monkeypatch.setattr(cli, "ensure_sudo", fake_ensure_sudo)
    monkeypatch.setattr(cli, "record_pyspy", fake_record_pyspy)
    monkeypatch.setattr(cli, "generate_load", fake_generate_load)
    monkeypatch.setattr(sys, "argv", ["flamelink", "profile", "python", "--pid", "1234", "--url", URL,
                                      "--rps", "0", "--out", str(tmp_path / "profile.svg"),
                                      "--report", str(tmp_path / "report.json")])

    with pytest.raises(SystemExit) as e:
        cli.main()
    assert e.value.code == 2  # argparse's exit code for usage errors
    assert "--rps" in capsys.readouterr().err
    assert started == []  # No sudo prompt, no profiler, no load


def test_profile_node_zero_duration_is_rejected_before_clinic(monkeypatch, capsys, tmp_path):
    # Before, a bad value stopped clinic right after it started, and clinic's own error
    # then replaced the real one. Everything is faked so a broken check fails fast.
    started = []

    def fake_record_clinicjs(**kwargs):
        started.append("record")

    async def fake_wait_until_ready(url):
        pass

    async def fake_generate_load(url, rps, duration_s):
        started.append("load")
        return [], {}

    monkeypatch.setattr(cli, "record_clinicjs", fake_record_clinicjs)
    monkeypatch.setattr(cli, "wait_until_ready", fake_wait_until_ready)
    monkeypatch.setattr(cli, "generate_load", fake_generate_load)
    monkeypatch.setattr(sys, "argv", ["flamelink", "profile", "node", "--url", NODE_URL, "--duration", "0",
                                      "--out", str(tmp_path / "flame.html"), "--report", str(tmp_path / "report.json"),
                                      "--", "node", "server.js"])

    with pytest.raises(SystemExit) as e:
        cli.main()
    assert e.value.code == 2
    assert "--duration" in capsys.readouterr().err
    assert started == []  # clinic never launched
