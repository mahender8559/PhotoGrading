FROM python:3.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/tmp \
    PHOTOGRADING_DATA_DIR=/data \
    STREAMLIT_CONFIG_DIR=/tmp/.streamlit \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_MAX_UPLOAD_SIZE=512 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

RUN apt-get update \
    && apt-get install -y --no-install-recommends libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 10001 photograding \
    && useradd --uid 10001 --gid 10001 --create-home --home-dir /home/photograding photograding

WORKDIR /app

COPY requirements.txt ./
RUN python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt

COPY --chown=10001:10001 . /app
RUN mkdir -p /data/recipes /data/masks \
    && chown -R 10001:10001 /data /home/photograding

USER 10001:10001

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=4)" || exit 1

CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true", "--server.maxUploadSize=512", "--browser.gatherUsageStats=false"]
