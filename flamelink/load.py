import httpx
import asyncio
import time

async def generate_load(url: str, rps: int, duration_s: int) -> tuple[list[float], int]:
    semaphore = asyncio.Semaphore(rps)
    response_times = []
    error_count = 0
    interval = 1 / rps
    async def make_request(client: httpx.AsyncClient):
        async with semaphore:
            start_time = time.perf_counter()
            try:
                response = await client.get(url)
            except httpx.RequestError as e:
                print(f"Request failed: {type(e).__name__}: {e}")
                nonlocal error_count
                error_count += 1
                return
            elapsed_time = (time.perf_counter() - start_time) * 1000
            response_times.append(elapsed_time)

    async with httpx.AsyncClient(timeout=30.0) as client:
        tasks = []
        start_time = time.perf_counter()
        next_tick = start_time

        while time.perf_counter() - start_time < duration_s:
            tasks.append(asyncio.create_task(make_request(client)))
            next_tick += interval
            sleep_time = next_tick - time.perf_counter()
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
        
        await asyncio.gather(*tasks)
    
    return response_times, error_count

def calculate_percentiles(times: list[float]) -> dict:
    if not times:
        return {"p50": None, "p95": None, "p99": None}
    
    sorted_times = sorted(times)
    p50 = sorted_times[int(len(sorted_times) * 0.5)]
    p95 = sorted_times[int(len(sorted_times) * 0.95)]
    p99 = sorted_times[int(len(sorted_times) * 0.99)]
    return {"p50": p50, "p95": p95, "p99": p99}
