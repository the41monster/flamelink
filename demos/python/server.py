from fastapi import FastAPI
import time

from demos.python.utils import fib

app = FastAPI()

@app.get("/fib/")
def get_fib(n: int):
    return {"n": n, "fib": fib(n)}
    
@app.get("/sleep/")
def get_sleep(ms: int):
    time.sleep(ms/1000)
    return {"slept_for": ms}

@app.get("/cpu/")
def get_cpu(iterations: int):
    count = 0
    for i in range(iterations):
        count += 1
    return {"iterations": iterations, "count": count}
