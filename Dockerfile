# syntax=docker/dockerfile:1

# uv's official image includes Python and uv. Pin both for repeatable builds.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Install dependencies in a cacheable layer. This project is intentionally
# script-oriented (`tool.uv.package = false`), so there is no package to install.
COPY pyproject.toml ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev

COPY dpx3300_convert.py send_hpgl.py vpype.toml README.md playbook.md ./
RUN mkdir -p /app/input /app/output

# The default container behavior is conversion. Override the command to run
# send_hpgl.py when using a Linux serial device passed through with --device.
ENTRYPOINT ["uv", "run", "--no-sync", "python"]
CMD ["dpx3300_convert.py", "--help"]
