# Development environment — T01.1

Observed on 2026-11-17 (Asia/Shanghai), on the existing local checkout.
This is a local baseline inventory, not a deployment or inference qualification.

| Item | Observed result |
| --- | --- |
| OS | macOS 26.7.1, build 25G241 (`sw_vers`) |
| Architecture | x86_64 (`uname -m`) |
| CPU | Intel Core i5, 2 GHz, 4 cores reported by `system_profiler SPHardwareDataType` |
| RAM | 16 GB reported by `system_profiler` |
| Disk | 466 GiB total, 36 GiB available on workspace volume (`df -h .`); transient measurement |
| GPU | Intel Iris Plus Graphics, integrated, dynamic VRAM max 1536 MB, Metal supported |
| GPU driver | No separate driver version reported; no CUDA/inference stack installed or tested by this task |
| Python baseline | CPython 3.12.1, existing Homebrew interpreter; `.python-version` selects 3.12 |
| Other initial Python | `python3 --version`: 3.13.7; original project `.venv`: 3.15.2 |
| Git | 2.43.0 |
| uv | 0.13.8 (3d97a6aad, x86_64-apple-darwin) |
| Docker / Compose | `docker` not on PATH; neither needed for T01.1 |
| Skills used | Installed superpowers 7.0.1: executing-plans, test-driven-development, verification-before-completion; local scoped self-review, no delegation |

The sandbox denied `sysctl -n machdep.cpu.brand_string hw.memsize`; the profiler
also warned that CPU/cache sysctl queries were restricted. CPU/core details above
are the profiler's reported values, not independently confirmed measurements.
Machine serial numbers/UUIDs were excluded from the inventory.

## Reproducible package baseline

`uv sync` resolved 26 packages and installed 25, including this project, on Python
3.12.1 without changing the supplied dependency lower bounds. The lockfile is the
full version/hash record. Verified direct versions:

| Runtime | Version | Development | Version |
| --- | --- | --- | --- |
| pydantic | 2.14.3 | pytest | 9.2.0 |
| openpyxl | 3.1.5 | pytest-cov | 7.1.0 |
| python-docx | 1.2.0 | ruff | 0.17.5 |
| PyYAML | 6.0.3 | uv_build (build backend) | 0.13.8 |
| httpx | 0.28.1 | | |

The installed package imports as `busconfig`; distribution metadata remains
`ai-func-config==0.1.0`. Doctor's verified default report has environment
`development`, model mode `disabled`, data path `runtime/data`, and `writable: true`.

## Reproduction and sandbox notes

```sh
uv sync --locked
uv run python --version
uv run python -c 'import busconfig'
uv run busconfig doctor
uv run pytest -q
uv run ruff check .
```

The initial sandbox invocation could not write the default uv cache. Subsequent
sandbox checks set `UV_CACHE_DIR=/tmp/busconfig-uv-cache`. Initial dependency
resolution with that cache hit blocked DNS; approved `uv sync` outside the sandbox
then succeeded. No application-network permission or service connection is needed.
`uv build --out-dir /tmp/busconfig-t011-dist` also succeeded using the build backend.

Only this macOS/Python combination has been exercised. Other platforms, a clean
machine, Docker, model inference and database connectivity remain unverified.
