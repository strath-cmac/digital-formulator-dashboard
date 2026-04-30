FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# API backend URL — override at runtime with:
#   docker run -e API_BASE_URL=http://<host>:8080 ...
# The sibling DM2-System-of-Models FastAPI service exposes port 8080 by default.
ENV API_BASE_URL=http://localhost:8080

EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

ENTRYPOINT ["streamlit", "run", "app.py", \
            "--server.port=8501", \
            "--server.address=0.0.0.0", \
            "--server.headless=true"]
