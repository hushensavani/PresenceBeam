FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV IS_DOCKER=1

WORKDIR /app

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ /app/src/

# Run the sync engine
CMD ["python", "src/main.py"]
