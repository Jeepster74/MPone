# 1. BUILD FRONTEND (Node)
FROM node:20-slim AS frontend-build
WORKDIR /app/frontend

COPY frontend/package.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# 2. RUNTIME (Python + Nginx)
FROM python:3.12-slim
WORKDIR /app

# Install dependencies
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend
COPY backend/ ./backend

# Copy built frontend (Static files)
COPY --from=frontend-build /app/frontend/dist ./static

# Expose port (Cloud Run uses 8080 by default, but we'll use $PORT)
ENV PORT=8080
EXPOSE 8080
CMD uvicorn backend.main:app --host 0.0.0.0 --port ${PORT}
