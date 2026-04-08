FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY learning_bot.py .
COPY learning_bot_files.zip .
RUN unzip learning_bot_files.zip

CMD ["python", "learning_bot.py"]
