FROM node:22-alpine AS web
WORKDIR /web
COPY package*.json ./
RUN npm ci --no-audit --no-fund
COPY index.html github-start.html city-explorer.html vite.config.js ./
COPY src ./src
COPY public ./public
RUN npm run build
FROM python:3.11-slim
WORKDIR /app
COPY services/api/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY services ./services
COPY apps ./apps
COPY data ./data
COPY --from=web /web/dist ./dist
RUN useradd -u 10001 -m codeverse
USER 10001:10001
EXPOSE 8000
CMD ["uvicorn","services.api.main:app","--host","0.0.0.0","--port","8000","--no-access-log"]
