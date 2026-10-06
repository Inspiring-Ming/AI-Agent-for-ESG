# Agent service and MCP servers (one image, three entry points).
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY agentic ./agentic
COPY mcp_servers ./mcp_servers
COPY service ./service
COPY ui ./ui
COPY figures ./figures
COPY *.py ./
