FROM python:3.11-slim

WORKDIR /app

COPY api_server.py /app/api_server.py
RUN chmod +x /app/api_server.py

EXPOSE 8181

CMD ["python3", "/app/api_server.py"]

