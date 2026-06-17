FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1
# Required to allow OAuth over HTTP (localhost only — not for production HTTPS)
ENV OAUTHLIB_INSECURE_TRANSPORT=1

EXPOSE 8643

CMD ["python", "app.py"]
