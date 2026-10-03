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

COPY hpgl_placement.py logical_layer_contract.py pen_plan.py svg_pen_contract.py ./
COPY penplan.schema.json vpype.toml README.md ./
COPY scripts/__init__.py scripts/booklet_impose.py scripts/dpx3300_convert.py scripts/job_preflight.py scripts/send_hpgl.py ./scripts/
RUN mkdir -p /app/input /app/output

# The default container behavior is conversion. Override the command to run
# send_hpgl.py when using a Linux serial device passed through with --device.
ENTRYPOINT ["uv", "run", "--no-sync", "python"]
CMD ["scripts/dpx3300_convert.py", "--help"]
