#!/usr/bin/env python3
import os
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, unquote, quote
import urllib.parse
from datetime import datetime

VIDEO_DIR = "/videos"
STATUS_FILE = "/videos/.conversion_status.json"
PORT = 8181

def format_file_size(size_bytes):
    """Форматировать размер файла в читаемый вид"""
    for unit in ['Б', 'КБ', 'МБ', 'ГБ', 'ТБ']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} ПБ"

def get_video_files(directory):
    """Получить список видеофайлов с метаданными"""
    video_files = []
    if not os.path.exists(directory):
        return video_files
    
    for root, dirs, files in os.walk(directory):
        for file in files:
            if Path(file).suffix.lower() == '.mp4':
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, directory)
                
                try:
                    stat = os.stat(file_path)
                    file_size = stat.st_size
                    mtime = stat.st_mtime
                    
                    video_files.append({
                        'name': relative_path,
                        'size': file_size,
                        'size_formatted': format_file_size(file_size),
                        'date': datetime.fromtimestamp(mtime).isoformat(),
                        'date_formatted': datetime.fromtimestamp(mtime).strftime('%d.%m.%Y %H:%M'),
                        'format': Path(file).suffix.lower().replace('.', '').upper()
                    })
                except OSError:
                    # Пропускаем файлы, к которым нет доступа
                    continue
    
    # Сортируем по дате (новые сначала)
    return sorted(video_files, key=lambda x: x['date'], reverse=True)

class VideoAPIHandler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        """Обработка HEAD запросов"""
        self._handle_request(send_body=False)
    
    def do_GET(self):
        """Обработка GET запросов"""
        self._handle_request(send_body=True)
    
    def _handle_request(self, send_body=True):
        # Обрабатываем /videos и /api/videos (через прокси)
        if self.path == '/videos' or self.path == '/videos/' or self.path == '/api/videos' or self.path == '/api/videos/':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            videos = get_video_files(VIDEO_DIR)
            response = json.dumps(videos, ensure_ascii=False)
            if send_body:
                self.wfile.write(response.encode('utf-8'))
        elif self.path == '/status' or self.path == '/status/' or self.path == '/api/status' or self.path == '/api/status/':
            # Возвращаем статус конвертации
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            status = {
                "active": False,
                "current_file": None,
                "progress": 0,
                "speed": None,
                "eta": None,
                "status": "idle"
            }
            
            if os.path.exists(STATUS_FILE):
                try:
                    with open(STATUS_FILE, 'r', encoding='utf-8') as f:
                        status = json.load(f)
                except:
                    pass
            
            response = json.dumps(status, ensure_ascii=False)
            if send_body:
                self.wfile.write(response.encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        # Упрощенное логирование
        pass

def main():
    server = HTTPServer(('0.0.0.0', PORT), VideoAPIHandler)
    print(f"API сервер запущен на порту {PORT}")
    print(f"Сканирование директории: {VIDEO_DIR}")
    server.serve_forever()

if __name__ == "__main__":
    main()

