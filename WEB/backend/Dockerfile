FROM python:3.11-slim

# Install ffmpeg and clean apt cache
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all backend files
COPY . .

# HuggingFace Space default port
EXPOSE 7860

CMD ["python", "app.py"]
