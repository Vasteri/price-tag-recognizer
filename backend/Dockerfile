FROM python:3.12.12-alpine3.22

ENV PYTHONPATH=/app
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN addgroup -g 1000 -S app \
    && adduser  -u 1000 -S -G app -s /sbin/nologin -h /app app
RUN mkdir -p /shared/uploads /shared/results \
    && chown -R 1000:1000 /shared /app
USER 1000:1000

COPY --chown=1000:1000 ./src ./src

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://127.0.0.1:8000/health || exit 1

EXPOSE 8000
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]