FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HF_HOME=/app/var/hf
WORKDIR /app
# INSTALL_RAG=0 builds a small image that uses lexical retrieval only.
ARG INSTALL_RAG=1
COPY requirements.txt requirements-rag.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
 && if [ "$INSTALL_RAG" = "1" ]; then pip install --no-cache-dir -r requirements-rag.txt; fi
COPY app ./app
COPY data ./data
RUN useradd --create-home --uid 1000 uds && mkdir -p /app/var && chown -R uds /app/var
USER uds
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --retries=5 CMD python -c "import urllib.request as u; u.urlopen('http://localhost:8000/api/health')"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
