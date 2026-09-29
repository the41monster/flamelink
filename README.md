# Flamelink
Live profiler orchestrator for Python/Node.js processes.

## Comparison of profiling process (py-spy:python vs clinic:node.js)
### py-spy
- Uses ptrace to attach to an already running process and sample the stack traces of all threads.
- Can be used to profile any Python process without modifying the code or restarting the process.
- It needs `sudo` privilege, or `--cap-add=SYS_PTRACE` in docker container to attach to the process.
- Stops itself after a `duration` and generates a flamegraph.

### clinic.js
- Uses `clinic` to profile a node.js process.
- Can not attach to an already running process, it needs to start the process with `clinic` and then stop it after a `duration`.
- No need for `sudo` privilege or `--cap-add=SYS_PTRACE` in docker container to profile the process.
- Server never stops itself, so flamelink stops it with `SIGINT` to the whole process group after a `duration`.
- Output location is controlled with `--dest` and `--name` flags

### Other important points
- Target needs to be under load for profiling to be effective, otherwise the flamegraph will be empty or nearly empty.