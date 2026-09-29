import time
import httpx

import asyncio
import pytest

from flamelink.load import generate_load
from flamelink.profilers.clinicjs import record
from flamelink.hotspot import parse_clinic_report, rank_clinic_hotspots


@pytest.mark.asyncio
async def test_clinicjs_captures_load(tmp_path):
    output_path = tmp_path / "report.html"

    LOAD_DURATION_S = 5
    # record()'s duration clock starts at Popen, before the readiness poll finishes.
    # Keep this ahead of LOAD_DURATION_S so a slow clinic/node startup can't push
    # load generation past when record() sends SIGINT.
    RECORD_DURATION_S = LOAD_DURATION_S + 10
    
    record_task = asyncio.create_task(asyncio.to_thread(
        record,
        command=["node", "demos/node/server.js"],
        duration=RECORD_DURATION_S,
        output_path=output_path,
    ))
    

    # readiness check
    async with httpx.AsyncClient() as client:
        deadline = time.monotonic() + 10  # 10 seconds from now
        ready = False
        while not ready:
            try:
                await client.get("http://localhost:3000/cpu/?iterations=1", timeout=0.1)
                ready = True
            except (httpx.RequestError, httpx.HTTPStatusError):
                if time.monotonic() > deadline:
                    raise RuntimeError("server not ready after 10 seconds")
                await asyncio.sleep(0.05)
    
    load_task = generate_load(
        url="http://localhost:3000/fib?n=38",
        rps=5,
        duration_s=LOAD_DURATION_S,
    )

    await asyncio.gather(record_task, load_task)

    assert output_path.exists(), "Clinic.js report was not generated"
    assert output_path.stat().st_size > 0, "Clinic.js report is empty"
    
    clinic_hotspots = parse_clinic_report(output_path)
    assert isinstance(clinic_hotspots, dict), "Parsed clinic report is not a dictionary"

    ranked_hotspots = rank_clinic_hotspots(clinic_hotspots)
    contains = False
    for hotspot in ranked_hotspots:
        if "fib" in hotspot["name"] and hotspot["category"] == "app":
            contains = True
            break
    assert contains, "Ranked hotspots do not contain the expected 'fib' function"
