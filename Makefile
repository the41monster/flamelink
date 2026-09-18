SHELL := /bin/bash
run-python:
	echo "Running Python demo..."
	uvicorn demos.python.server:app --workers 1

run-node:
	echo "Running Node.js demo..."
	cd demos/node && node server.js

profile-node:
	echo "Profiling Node.js demo..."
	cd demos/node && clinic flame -- node server.js

load-python-50:
	python3 -m flamelink.cli load --url http://localhost:8000/sleep/?ms=100 --rps 50 --duration 10

load-python-100:
	python3 -m flamelink.cli load --url http://localhost:8000/sleep/?ms=100 --rps 100 --duration 10

load-python-200:
	python3 -m flamelink.cli load --url http://localhost:8000/sleep/?ms=100 --rps 200 --duration 10

load-node-50:
	python3 -m flamelink.cli load --url http://localhost:3000/sleep/?ms=100 --rps 50 --duration 10

load-node-100:
	python3 -m flamelink.cli load --url http://localhost:3000/sleep/?ms=100 --rps 100 --duration 10

load-node-200:
	python3 -m flamelink.cli load --url http://localhost:3000/sleep/?ms=100 --rps 200 --duration 10

test-pyspy:
	uv run pytest tests/test_pyspy_integration.py -v
