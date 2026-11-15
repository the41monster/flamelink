import asyncio
import threading
import time

import pytest

from flamelink import cli
from flamelink.profilers.errors import ProfilerError

URL = "http://localhost:3000/fib/?n=25"
COMMAND = ["node", "server.js"]
OUT = "flame.html"

# How long a fake clinic waits for the stop signal. If stop_event.set() is ever
# missing, tests fail after this long instead of hanging forever.
STOP_WAIT_S = 2


def fake_clinic(seen: dict):
    # Stands in for clinic's record(): runs in the worker thread and blocks
    # until the caller sets stop_event, like the real event mode does
    def record(**kwargs):
        seen["kwargs"] = kwargs
        seen["stopped"] = kwargs["stop_event"].wait(timeout=STOP_WAIT_S)
    return record


@pytest.mark.asyncio
async def test_waits_for_server_then_loads_then_stops_clinic(monkeypatch):
    calls = []
    seen = {}

    async def fake_ready(url):
        calls.append(("ready", url))

    async def fake_load(url, rps, duration_s):
        calls.append(("load", url, rps, duration_s))
        return [1.0], {}

    monkeypatch.setattr(cli, "record_clinicjs", fake_clinic(seen))
    monkeypatch.setattr(cli, "wait_until_ready", fake_ready)
    monkeypatch.setattr(cli, "generate_load", fake_load)

    result = await cli.record_clinic_with_load(COMMAND, OUT, URL, rps=10, duration_s=5)

    # Only ready-vs-load order is checked: when the clinic thread starts is up to the scheduler
    assert calls == [("ready", URL), ("load", URL, 10, 5)]
    assert result == ([1.0], {})

    kwargs = seen["kwargs"]
    assert kwargs["command"] == COMMAND
    assert kwargs["output_path"] == OUT
    assert kwargs["duration"] == 5
    assert kwargs["mode"] == "flame"
    # record() checks the event from a worker thread, so it must be a thread-safe one
    assert isinstance(kwargs["stop_event"], threading.Event)
    assert seen["stopped"] is True


@pytest.mark.asyncio
async def test_clinic_is_stopped_even_when_load_fails(monkeypatch):
    seen = {}

    async def fake_ready(url):
        pass

    async def fake_load(url, rps, duration_s):
        raise RuntimeError("boom")

    monkeypatch.setattr(cli, "record_clinicjs", fake_clinic(seen))
    monkeypatch.setattr(cli, "wait_until_ready", fake_ready)
    monkeypatch.setattr(cli, "generate_load", fake_load)

    with pytest.raises(RuntimeError, match="boom"):
        await cli.record_clinic_with_load(COMMAND, OUT, URL, rps=10, duration_s=5)

    # Without this, a failed load would leave clinic and the Node server running
    assert seen["stopped"] is True


@pytest.mark.asyncio
async def test_clinic_error_wins_over_not_ready(monkeypatch):
    # When clinic dies on startup the server never comes up, so the readiness
    # check fails too. The user should see the cause (clinic), not the symptom.
    def crashing_clinic(**kwargs):
        raise ProfilerError("exited early")

    async def fake_ready(url):
        raise ProfilerError("not ready")

    # A flag, not pytest.fail(): the clinic error raised in the finally would replace
    # pytest.fail's exception, so the guard would never show up
    load_started = []

    async def fake_load(url, rps, duration_s):
        load_started.append(True)
        return [], {}

    monkeypatch.setattr(cli, "record_clinicjs", crashing_clinic)
    monkeypatch.setattr(cli, "wait_until_ready", fake_ready)
    monkeypatch.setattr(cli, "generate_load", fake_load)

    with pytest.raises(ProfilerError, match="exited early"):
        await cli.record_clinic_with_load(COMMAND, OUT, URL, rps=10, duration_s=5)
    assert load_started == []   # the server never became ready, so no load


@pytest.mark.asyncio
async def test_clinic_failure_is_reported_without_waiting_for_readiness(monkeypatch):
    # Clinic fails at once (e.g. not on PATH), but nothing will ever listen on the URL.
    # The error must come out straight away, not after the readiness timeout.
    def crashing_clinic(**kwargs):
        raise ProfilerError("clinic not installed")

    async def slow_ready(url):
        await asyncio.sleep(5)  # Stands in for polling a port that never opens

    async def fake_load(url, rps, duration_s):
        return [], {}

    monkeypatch.setattr(cli, "record_clinicjs", crashing_clinic)
    monkeypatch.setattr(cli, "wait_until_ready", slow_ready)
    monkeypatch.setattr(cli, "generate_load", fake_load)

    start = time.perf_counter()
    with pytest.raises(ProfilerError, match="clinic not installed"):
        await cli.record_clinic_with_load(COMMAND, OUT, URL, rps=10, duration_s=5)
    assert time.perf_counter() - start < 1


@pytest.mark.asyncio
async def test_clinic_exiting_cleanly_before_ready_is_an_error(monkeypatch):
    # e.g. `-- node -e 1`: clinic finishes without an error, but no server ever came up,
    # so there is nothing to send load to
    load_started = []

    def quick_clinic(**kwargs):
        return None

    async def slow_ready(url):
        await asyncio.sleep(5)

    async def fake_load(url, rps, duration_s):
        load_started.append(True)
        return [], {}

    monkeypatch.setattr(cli, "record_clinicjs", quick_clinic)
    monkeypatch.setattr(cli, "wait_until_ready", slow_ready)
    monkeypatch.setattr(cli, "generate_load", fake_load)

    with pytest.raises(ProfilerError, match="exited before the server was ready"):
        await cli.record_clinic_with_load(COMMAND, OUT, URL, rps=10, duration_s=5)
    assert load_started == []
