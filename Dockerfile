FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS base

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies first so source edits do not invalidate the dependency layer.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-install-project

COPY finrl_eval ./finrl_eval
COPY scripts ./scripts
COPY tests ./tests
COPY rl ./rl
COPY case_study ./case_study
RUN uv sync --frozen

RUN useradd --create-home --uid 1000 finrl && mkdir -p /app/runs && chown -R finrl:finrl /app
USER finrl
VOLUME ["/app/runs"]

ENTRYPOINT ["finrl-eval"]
CMD ["list"]
