import httpx
import pytest

import flamelink.load as load
from flamelink.load import wait_until_ready
from flamelink.profilers.errors import ProfilerError

URL = "http://localhost:3000/"
RealAsyncClient = httpx.AsyncClient


def fake_server(monkeypatch, respond):
    """Route wait_until_ready's requests to `respond(request, call_number)` instead of the network.

    Returns a list that gets one entry per request, so tests can count attempts.
    """
    calls = []

    def handler(request):
        calls.append(request)
        return respond(request, len(calls))

    def make_client(**kwargs):
        return RealAsyncClient(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(load.httpx, "AsyncClient", make_client)
    return calls


@pytest.mark.asyncio
async def test_retries_connect_error_until_server_is_up(monkeypatch):
    def respond(request, n):
        if n <= 2:
            raise httpx.ConnectError("connection refused", request=request)
        return httpx.Response(200)

    calls = fake_server(monkeypatch, respond)
    await wait_until_ready(URL, timeout_s=5)
    assert len(calls) == 3


@pytest.mark.asyncio
async def test_raises_when_server_never_comes_up(monkeypatch):
    def respond(request, n):
        raise httpx.ConnectError("connection refused", request=request)

    calls = fake_server(monkeypatch, respond)
    with pytest.raises(ProfilerError, match="did not become ready"):
        await wait_until_ready(URL, timeout_s=0.2)
    assert len(calls) > 1  # It retried before giving up


@pytest.mark.asyncio
async def test_error_response_counts_as_ready(monkeypatch):
    # A 500 still means something is listening and answering; that's all readiness needs
    calls = fake_server(monkeypatch, lambda request, n: httpx.Response(500))
    await wait_until_ready(URL, timeout_s=5)
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_read_timeout_counts_as_ready(monkeypatch):
    # The connection was accepted and the server is just slow to answer, so it's up
    def respond(request, n):
        raise httpx.ReadTimeout("slow", request=request)

    calls = fake_server(monkeypatch, respond)
    await wait_until_ready(URL, timeout_s=5)
    assert len(calls) == 1
