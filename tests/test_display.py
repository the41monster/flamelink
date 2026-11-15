from rich.console import Console

from flamelink.display import DEFAULT_TOP, render_report
from flamelink.report import build_report

TARGET = "http://localhost:8000/fib"
TIMES = [10.0, 20.0, 30.0]

# Same rows as PYSPY_EXPECTED in test_reporters.py, written out here so test files don't import each other
PYSPY_ROWS = [
    {"fn": "fib",  "file": "app.py", "line": 5, "self_pct": 80.0, "total_pct": 80.0},
    {"fn": "idle", "file": "app.py", "line": 9, "self_pct": 20.0, "total_pct": 20.0},
    {"fn": "main", "file": "app.py", "line": 1, "self_pct": 0.0,  "total_pct": 100.0},
]


def render(report: dict) -> str:
    # record=True keeps what was printed; a fixed width makes line wrapping the same every run
    console = Console(record=True, width=100)
    render_report(report, console)
    return console.export_text()


def test_table_renders():
    report = build_report(TARGET, 10, TIMES, sampler="py-spy", hotspots=PYSPY_ROWS)
    out = render(report)

    assert "fib" in out
    assert "app.py:5" in out
    assert "80.00" in out
    assert "100.00" in out


def test_brackets_and_file_without_line_come_through_literally():
    rows = [
        {"fn": "[SHARED_LIB]", "file": "/usr/bin/node", "line": None, "self_pct": 20.0, "total_pct": 30.0},
        # Node's name for code run with `node -e`. Rich reads a lowercase [tag] as a style,
        # so without escape() this name would silently vanish. [SHARED_LIB] is safe either way,
        # because Rich ignores tags that start with an uppercase letter.
        # file is plain on purpose: "[eval]" in the location column would let the assert pass
        # even if the function column lost its escape()
        {"fn": "[eval]", "file": "cli.js", "line": 1, "self_pct": 10.0, "total_pct": 10.0},
    ]
    report = build_report(TARGET, 10, TIMES, sampler="clinic", hotspots=rows)
    out = render(report)

    assert "[SHARED_LIB]" in out
    assert "[eval]" in out          # escape() kept Rich from reading it as a style tag
    assert "/usr/bin/node" in out
    assert ":None" not in out       # no line means no ":line" suffix


def test_table_is_capped_at_default_top():
    total = DEFAULT_TOP + 5
    # Zero-padded names so no name is a substring of another (fn_2 would match inside fn_20)
    rows = [
        {"fn": f"fn_{i:02d}", "file": "app.py", "line": i + 1, "self_pct": float(total - i), "total_pct": float(total - i)}
        for i in range(total)
    ]
    report = build_report(TARGET, 10, TIMES, sampler="py-spy", hotspots=rows)
    out = render(report)

    assert f"Showing top {DEFAULT_TOP} of {total}" in out
    assert f"fn_{DEFAULT_TOP - 1:02d}" in out   # row 20, the last one shown
    assert f"fn_{DEFAULT_TOP:02d}" not in out   # row 21, the first one cut
