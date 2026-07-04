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
