FROM jrottenberg/ffmpeg:4.4-ubuntu

# Устанавливаем зависимости для Python и проверяем поддержку QSV
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Проверяем, что ffmpeg поддерживает QSV (вывод будет в логах при первом запуске)
RUN ffmpeg -hide_banner -encoders 2>/dev/null | grep -q h264_qsv || echo "QSV может быть недоступен, будет использован программный кодек"

WORKDIR /app

COPY convert.py /app/convert.py
RUN chmod +x /app/convert.py

ENTRYPOINT []
CMD ["python3", "-u", "/app/convert.py"]

