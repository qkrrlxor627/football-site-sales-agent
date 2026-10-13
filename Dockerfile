# 1) 화면 빌드
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# 2) 서버: API + 빌드된 화면을 한 프로세스로
FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    PITCHROOM_ENV=production PITCHROOM_HOST=0.0.0.0 PITCHROOM_PORT=8000 PITCHROOM_DB=/data/pitchroom.db
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py ./
COPY pitchroom/ ./pitchroom/
COPY --from=web /web/dist ./frontend/dist
RUN useradd --system --uid 10001 pitchroom && mkdir /data && chown pitchroom /data
USER pitchroom
VOLUME /data
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"
CMD ["python", "app.py"]
