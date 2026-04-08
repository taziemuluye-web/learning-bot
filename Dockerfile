FROM python:3.11-slim

# Install unzip and any other needed system packages
RUN apt-get update && apt-get install -y unzip && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY learning_bot.py .
COPY learning_bot_files.zip .

# Unzip the folder
RUN unzip learning_bot_files.zip

CMD ["python", "learning_bot.py"]
