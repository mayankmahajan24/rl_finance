# Task image: Python 3.12 with pinned analysis and time-series libraries; no network at run time.
FROM python:3.12-slim@sha256:191083cdf6c7bda8c76158983163ead5d5cf7b77cf3033e805bb0f5296f51b4b
COPY requirements.lock /tmp/requirements.lock
RUN pip install --no-cache-dir --no-deps -r /tmp/requirements.lock && pip check && rm /tmp/requirements.lock
ENV MPLBACKEND=Agg NUMBA_CACHE_DIR=/tmp/numba PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY data /app/data
RUN mkdir -p /app/output /app/solution
