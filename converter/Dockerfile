FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive

# Устанавливаем зависимости для сборки ffmpeg с QSV и Python
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    build-essential \
    yasm \
    cmake \
    libtool \
    libvpx-dev \
    libx264-dev \
    libx265-dev \
    libnuma-dev \
    libvorbis-dev \
    libopus-dev \
    libfdk-aac-dev \
    libmp3lame-dev \
    libass-dev \
    libfreetype6-dev \
    libmfx-dev \
    intel-media-va-driver-non-free \
    libva-dev \
    libva-drm2 \
    libva-x11-2 \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Скачиваем и собираем ffmpeg с поддержкой QSV
WORKDIR /tmp
RUN wget https://ffmpeg.org/releases/ffmpeg-4.4.tar.bz2 && \
    tar -xjf ffmpeg-4.4.tar.bz2 && \
    cd ffmpeg-4.4 && \
    ./configure \
        --enable-gpl \
        --enable-libx264 \
        --enable-libx265 \
        --enable-libvpx \
        --enable-libvorbis \
        --enable-libopus \
        --enable-libfdk-aac \
        --enable-libmp3lame \
        --enable-libass \
        --enable-libfreetype \
        --enable-libmfx \
        --enable-vaapi \
        --enable-nonfree \
        --enable-shared \
        --prefix=/usr/local && \
    make -j$(nproc) && \
    make install && \
    ldconfig && \
    cd / && \
    rm -rf /tmp/ffmpeg-4.4* && \
    apt-get purge -y build-essential yasm cmake libtool wget && \
    apt-get autoremove -y

WORKDIR /app

COPY convert.py /app/convert.py
RUN chmod +x /app/convert.py

ENTRYPOINT []
CMD ["python3", "-u", "/app/convert.py"]

