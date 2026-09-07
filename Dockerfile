FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    LIVE_DATA=false

WORKDIR /app
COPY pyproject.toml requirements.txt README.md ./
COPY src ./src
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8000
CMD ["uvicorn", "mcp_agent.agent.main:app", "--host", "0.0.0.0", "--port", "8000"]
