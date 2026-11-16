# ---- front-end dependency: fetched from npm and copied to static/vendor (no CDN at runtime) ----
FROM node:22-alpine AS vendor
WORKDIR /v
COPY vendor-src/package.json vendor-src/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY vendor-src/ ./
RUN sh build.sh /out

FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /srv
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app ./app
COPY static ./static
COPY --from=vendor /out/ ./static/vendor/
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
