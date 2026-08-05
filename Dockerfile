FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /workspace

COPY pyproject.toml README.md ./
COPY config ./config
COPY src ./src
COPY tests ./tests

RUN python -m pip install --no-cache-dir -e ".[dev]"

CMD ["python", "-m", "pytest", "--cov=cryptopulse", "--cov-report=term-missing"]
