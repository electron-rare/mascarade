FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

# Specs directory is expected to be mounted via a volume at runtime
# Default: /workspace/.auto-claude/specs
ENV SPECS_DIR=/workspace/.auto-claude/specs
ENV HOST=0.0.0.0
ENV PORT=3200
# BRIDGE_API_KEY — set this in docker-compose or as a secret

EXPOSE 3200

CMD ["python", "main.py"]
