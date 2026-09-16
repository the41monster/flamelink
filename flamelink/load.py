import httpx
import asyncio
import time

async def generate_load(url: str, rps: int, duration_s: int) -> tuple[list[float], dict]:
    semaphore = asyncio.Semaphore(rps)
    response_times = []
    error_dict = {}
    interval = 1 / rps
    async def make_request(client: httpx.AsyncClient):
        async with semaphore:
            start_time = time.perf_counter()
            try:
                response = await client.get(url)
                response.raise_for_status()
                elapsed_time = (time.perf_counter() - start_time) * 1000
                response_times.append(elapsed_time)
            except httpx.TimeoutException:
                error_dict["timeout"] = error_dict.get("timeout", 0) + 1
            except httpx.ConnectError:
                error_dict["connection_refused"] = error_dict.get("connection_refused", 0) + 1
            except httpx.HTTPStatusError as e:
                error_dict["http_error"] = error_dict.get("http_error", 0) + 1
            except httpx.RequestError as e:
                error_dict["request_error"] = error_dict.get("request_error", 0) + 1
            

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
    
    return response_times, error_dict

def calculate_percentiles(times: list[float]) -> dict:
    if not times:
        return {"p50": None, "p95": None, "p99": None}
    
    sorted_times = sorted(times)
    p50 = sorted_times[int(len(sorted_times) * 0.5)]
    p95 = sorted_times[int(len(sorted_times) * 0.95)]
    p99 = sorted_times[int(len(sorted_times) * 0.99)]
    return {"p50": p50, "p95": p95, "p99": p99}
