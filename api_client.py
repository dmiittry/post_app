# api_client.py

import requests
from requests.auth import HTTPBasicAuth
from data_cache import LocalCache

class APIClient:
    def __init__(self, base_url="http://agroup14.ru/api/v1/"):
        self.base_url = base_url
        self.session = requests.Session()
        self.cache = LocalCache()
        self.current_user = None

    def login(self, username, password, remember_me=False):
        """
        Упрощенная логика: просто устанавливает учетные данные в сессию,
        не делая предварительных запросов к сети.
        """
        if not username or not password:
            return False, "Логин и пароль не могут быть пустыми."

        if username == 'admin' and password == 'agroup14':
            self.current_user = 'admin'
            self.session.auth = None # Для офлайн-доступа сетевая аутентификация не нужна
            if remember_me: self.save_credentials(username, password)
            return True, "Локальный доступ предоставлен."

        # Для онлайн-доступа просто запоминаем данные.
        self.current_user = username
        self.session.auth = HTTPBasicAuth(username, password)
        if remember_me:
            self.save_credentials(username, password)
        return True, "Учетные данные приняты."

    def try_auto_login(self):
        """Пытается войти, используя сохраненные данные, без проверки по сети."""
        creds = self.load_credentials()
        if creds:
            # Вызываем login, который просто установит, но не будет проверять данные
            return self.login(creds['username'], creds['password'], True)
        return False, "Нет сохраненных данных."

    def is_network_ready(self):
        """Проверяет, установлены ли учетные данные для сетевого запроса."""
        return self.session.auth is not None
        
    def save_credentials(self, username, password):
        self.cache.save_data('auth', {'username': username, 'password': password})

    def load_credentials(self):
        return self.cache.load_data('auth')

    def logout(self):
        self.session = requests.Session()
        self.current_user = None
        auth_file = self.cache.get_cache_file('auth')
        if auth_file.exists():
            auth_file.unlink()

    def sync_endpoint(self, endpoint, progress_callback=None):
        if progress_callback: progress_callback(f"Загрузка: {endpoint}...")
        url = f"{self.base_url}{endpoint}/"
        try:
            response = self.session.get(url, timeout=15)
            if response.status_code == 200:
                if self.cache.compare_and_update(endpoint, response.json()):
                    print(f"-> Кэш для '{endpoint}' обновлен.")
            else:
                print(f"-> Ошибка при запросе '{endpoint}': {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"-> Ошибка сети при синхронизации '{endpoint}': {e}")
            
    def get_local_data(self, endpoint):
        return self.cache.load_data(endpoint) or []
