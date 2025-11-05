# data_cache.py

import json
from pathlib import Path
import hashlib

class LocalCache:
    """
    Управляет сохранением и загрузкой данных в локальные JSON-файлы.
    """
    def __init__(self, cache_dir="cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)

    def get_cache_file(self, key):
        """Возвращает путь к файлу кэша для указанного ключа (эндпоинта)."""
        return self.cache_dir / f"{key.replace('/', '_')}.json"

    def load_data(self, key):
        """Загружает данные из файла кэша."""
        cache_file = self.get_cache_file(key)
        if not cache_file.exists():
            return None
        with open(cache_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def save_data(self, key, data):
        """Сохраняет данные в файл кэша."""
        with open(self.get_cache_file(key), 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def compare_and_update(self, key, new_data):
        """
        Сравнивает новые данные со старыми. Обновляет кэш, если есть разница.
        Возвращает True, если данные были обновлены.
        """
        old_data = self.load_data(key)
        
        # Простое сравнение словарей
        if old_data != new_data:
            self.save_data(key, new_data)
            return True
        return False
