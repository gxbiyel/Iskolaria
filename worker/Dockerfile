FROM python:3.12-slim AS base
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app

# test stage: Jenkins runs "docker build --target test"
FROM base AS test
RUN pip install --no-cache-dir pytest
COPY tests ./tests
RUN python -m pytest -q

FROM base AS production
RUN useradd --create-home appuser
USER appuser
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1
CMD ["python", "-m", "app.main"]