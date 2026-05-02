FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Koyeb needs a port exposed even for worker processes
EXPOSE 8000

# Run the bot
CMD ["python", "bot.py"]
