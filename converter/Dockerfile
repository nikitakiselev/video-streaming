FROM jrottenberg/ffmpeg:4.4-ubuntu

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY convert.py /app/convert.py
RUN chmod +x /app/convert.py

ENTRYPOINT []
CMD ["python3", "-u", "/app/convert.py"]

