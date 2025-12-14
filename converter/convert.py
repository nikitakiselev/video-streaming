#!/usr/bin/env python3
import os
import sys
import subprocess
import time
import json
import threading
from pathlib import Path

# Отключаем буферизацию вывода для корректного логирования в Docker
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

INPUT_DIR = "/input"
OUTPUT_DIR = "/output"
STATUS_FILE = "/output/.conversion_status.json"
SCAN_INTERVAL = 60  # секунд

# Поддерживаемые видео форматы
VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.3gp', '.ogv'}

# Глобальный статус конвертации
conversion_status = {
    "active": False,
    "current_file": None,
    "progress": 0,
    "speed": None,
    "eta": None,
    "status": "idle",
    "method": None  # "qsv" или "software"
}
status_lock = threading.Lock()

def save_status():
    """Сохранить статус в файл"""
    try:
        with status_lock:
            with open(STATUS_FILE, 'w', encoding='utf-8') as f:
                json.dump(conversion_status, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Ошибка сохранения статуса: {e}", flush=True)

def update_status(**kwargs):
    """Обновить статус конвертации"""
    with status_lock:
        conversion_status.update(kwargs)
    save_status()

def get_video_files(directory):
    """Получить список видеофайлов в директории (учитывая symlink-и)"""
    video_files = []
    # followlinks=True — обходим вложенные каталоги, даже если это symlink-и
    for root, dirs, files in os.walk(directory, followlinks=True):
        for file in files:
            if Path(file).suffix.lower() in VIDEO_EXTENSIONS:
                video_files.append(os.path.join(root, file))
    # Сортируем по алфавиту
    return sorted(video_files)

def get_output_path(input_path):
    """Получить путь к выходному файлу"""
    relative_path = os.path.relpath(input_path, INPUT_DIR)
    output_path = os.path.join(OUTPUT_DIR, relative_path)
    # Заменяем расширение на .mp4
    base_name = os.path.splitext(output_path)[0]
    return base_name + '.mp4'

def needs_conversion(input_path, output_path):
    """Проверить, нужна ли конвертация"""
    if not os.path.exists(output_path):
        return True
    
    # Проверяем, что выходной файл новее входного
    input_mtime = os.path.getmtime(input_path)
    output_mtime = os.path.getmtime(output_path)
    return input_mtime > output_mtime

def parse_ffmpeg_progress(line):
    """Парсить строку прогресса ffmpeg"""
    if '=' not in line:
        return None
    try:
        key, value = line.strip().split('=', 1)
        return {key.strip(): value.strip()}
    except:
        return None

def convert_video(input_path, output_path):
    """Конвертировать видео в MP4 (H.264, AAC)"""
    # Создаем директорию для выходного файла
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    filename = os.path.basename(input_path)
    print(f"Конвертация: {input_path} -> {output_path}", flush=True)
    
    update_status(
        active=True,
        current_file=filename,
        progress=0,
        speed=None,
        eta=None,
        status="starting"
    )
    
    # Получаем длительность видео для расчета прогресса
    duration = None
    try:
        probe_cmd = [
            'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1', input_path
        ]
        result = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
        duration = float(result.stdout.strip())
    except:
        pass
    
    # Проверяем доступность Quick Sync с подробным выводом
    use_qsv = False
    print("=== Проверка Intel Quick Sync ===", flush=True)
    
    # Проверка 1: наличие устройства
    if os.path.exists('/dev/dri/renderD128'):
        print("✓ Устройство /dev/dri/renderD128 найдено", flush=True)
        device_ok = True
    else:
        print("✗ Устройство /dev/dri/renderD128 не найдено", flush=True)
        device_ok = False
        if os.path.exists('/dev/dri'):
            dri_devices = [f for f in os.listdir('/dev/dri') if f.startswith('renderD')]
            if dri_devices:
                print(f"  Найдены другие устройства: {', '.join(dri_devices)}", flush=True)
                device_ok = True
            else:
                print("  В /dev/dri нет устройств renderD*", flush=True)
        else:
            print("  Директория /dev/dri не существует", flush=True)
    
    # Проверка 2: поддержка QSV в ffmpeg
    if device_ok:
        try:
            check_cmd = ['ffmpeg', '-hide_banner', '-encoders']
            result = subprocess.run(check_cmd, capture_output=True, text=True, timeout=5)
            if 'h264_qsv' in result.stdout:
                print("✓ Кодек h264_qsv доступен в ffmpeg", flush=True)
                use_qsv = True
            else:
                print("✗ Кодек h264_qsv НЕ найден в ffmpeg", flush=True)
                print("  Возможные причины:", flush=True)
                print("  - Образ ffmpeg не собран с поддержкой QSV", flush=True)
                print("  - Не установлены библиотеки Intel Media SDK", flush=True)
        except Exception as e:
            print(f"✗ Ошибка проверки ffmpeg: {e}", flush=True)
    else:
        print("✗ Устройство GPU недоступно, пропускаем проверку кодека", flush=True)
    
    if use_qsv:
        print(">>> Quick Sync будет использоваться <<<", flush=True)
    else:
        print(">>> Quick Sync НЕ будет использоваться, используется программный кодек <<<", flush=True)
    print("===================================", flush=True)
    
    # Параметры конвертации
    if use_qsv:
        update_status(method="qsv")
        # Для QSV инициализируем устройство и конвертируем формат пикселей
        cmd = [
            'ffmpeg',
            '-init_hw_device', 'qsv=hw:/dev/dri/renderD128',  # Инициализируем QSV устройство
            '-i', input_path,
            '-vf', 'format=nv12,hwupload=extra_hw_frames=64',  # Конвертируем в nv12 и загружаем в GPU
            '-c:v', 'h264_qsv',
            '-preset', 'medium',
            '-global_quality', '23',
            '-look_ahead', '1',
            '-c:a', 'aac',
            '-b:a', '192k',
            '-movflags', '+faststart',
            '-profile:v', 'high',
            '-level', '4.0',
            '-y',
            '-progress', 'pipe:1',
            '-loglevel', 'warning',  # Изменено на warning для диагностики
            output_path
        ]
    else:
        update_status(method="software")
        cmd = [
            'ffmpeg',
            '-i', input_path,
            '-c:v', 'libx264',           # Видеокодек H.264
            '-preset', 'medium',          # Баланс скорости/качества
            '-crf', '23',                 # Качество (18-28, меньше = лучше)
            '-c:a', 'aac',                # Аудиокодек AAC
            '-b:a', '192k',               # Битрейт аудио
            '-movflags', '+faststart',    # Быстрый старт для веб-плееров
            '-pix_fmt', 'yuv420p',        # Совместимость с браузерами
            '-profile:v', 'high',         # Профиль H.264
            '-level', '4.0',              # Уровень H.264
            '-y',                         # Перезаписать выходной файл
            '-progress', 'pipe:1',        # Вывод прогресса в stdout
            '-loglevel', 'error',         # Минимальный вывод логов
            output_path
        ]
    
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                                  text=True, bufsize=1)
        
        update_status(status="converting")
        
        # Читаем прогресс из stdout
        out_time = 0
        for line in process.stdout:
            line = line.strip()
            if not line or '=' not in line:
                continue
                
            try:
                if line.startswith('out_time_ms='):
                    out_time_ms = float(line.split('=', 1)[1])
                    out_time = out_time_ms / 1000000.0
                    if duration and duration > 0:
                        progress = min(100, int((out_time / duration) * 100))
                        update_status(progress=progress)
                elif line.startswith('speed='):
                    speed_str = line.split('=', 1)[1].replace('x', '').strip()
                    speed = float(speed_str)
                    update_status(speed=speed)
                    if duration and speed > 0 and out_time > 0:
                        remaining = max(0, (duration - out_time) / speed)
                        update_status(eta=int(remaining))
            except Exception as e:
                # Игнорируем ошибки парсинга
                pass
        
        process.wait()
        
        # Читаем stderr для диагностики ошибок
        stderr_output = process.stderr.read() if process.stderr else ""
        if stderr_output and (process.returncode != 0 or 'error' in stderr_output.lower() or 'failed' in stderr_output.lower()):
            print(f"FFmpeg stderr (ошибки): {stderr_output[:2000]}", flush=True)
        
        if process.returncode == 0:
            print(f"Успешно: {output_path}", flush=True)
            update_status(
                active=False,
                current_file=None,
                progress=100,
                status="completed",
                method=None
            )
            time.sleep(1)  # Показываем 100% на секунду
            update_status(
                active=False,
                current_file=None,
                progress=0,
                status="idle",
                method=None
            )
            return True
        else:
            raise subprocess.CalledProcessError(process.returncode, cmd)
            
    except subprocess.CalledProcessError as e:
        print(f"Ошибка конвертации {input_path}: {e}", flush=True)
        update_status(
            active=False,
            current_file=None,
            progress=0,
            status="error",
            method=None
        )
        time.sleep(2)
        update_status(status="idle", method=None)
        return False
    except Exception as e:
        print(f"Неожиданная ошибка: {e}", flush=True)
        update_status(
            active=False,
            current_file=None,
            progress=0,
            status="error",
            method=None
        )
        time.sleep(2)
        update_status(status="idle", method=None)
        return False

def scan_and_convert():
    """Сканировать входную директорию и конвертировать файлы"""
    if not os.path.exists(INPUT_DIR):
        print(f"Входная директория не найдена: {INPUT_DIR}", flush=True)
        return
    
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    video_files = get_video_files(INPUT_DIR)
    print(f"Найдено видеофайлов: {len(video_files)}", flush=True)
    
    for input_path in video_files:
        output_path = get_output_path(input_path)
        
        if needs_conversion(input_path, output_path):
            convert_video(input_path, output_path)
        else:
            print(f"Пропуск (уже обработан): {input_path}", flush=True)

def main():
    """Главная функция"""
    print("Сервис конвертации видео запущен", flush=True)
    print(f"Входная директория: {INPUT_DIR}", flush=True)
    print(f"Выходная директория: {OUTPUT_DIR}", flush=True)
    print(f"Интервал сканирования: {SCAN_INTERVAL} секунд", flush=True)
    
    # Инициализируем статус
    update_status(
        active=False,
        current_file=None,
        progress=0,
        speed=None,
        eta=None,
        status="idle",
        method=None
    )
    
    # Первоначальное сканирование
    scan_and_convert()
    
    # Периодическое сканирование
    while True:
        time.sleep(SCAN_INTERVAL)
        print(f"\n--- Сканирование (интервал {SCAN_INTERVAL}с) ---", flush=True)
        scan_and_convert()

if __name__ == "__main__":
    main()

