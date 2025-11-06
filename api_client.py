# api_client.py

import requests
from requests.auth import HTTPBasicAuth
from data_cache import LocalCache
import json

class APIClient:
    def __init__(self, base_url="https://agroup14.ru/api/v1/"):  # ИЗМЕНЕНО: HTTPS
        self.base_url = base_url
        self.session = requests.Session()
        self.cache = LocalCache()
        self.current_user = None
        self.on_data_updated_callback = None  # НОВОЕ: колбэк для обновления UI

    def set_data_updated_callback(self, callback):
        """Устанавливает функцию, которая будет вызвана при обновлении данных"""
        self.on_data_updated_callback = callback

    def login(self, username, password, remember_me=False):
        if not username or not password:
            return False, "Логин и пароль не могут быть пустыми."
        
        self.current_user = username
        self.session.auth = HTTPBasicAuth(username, password)
        
        try:
            response = self.session.get(f"{self.base_url}seasons/", timeout=10)
            if response.status_code in [401, 403]:
                self.session.auth = None
                return False, "Неверный логин или пароль."
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            self.session.auth = None
            return False, f"Ошибка сети: {e}"
        
        if remember_me:
            self.save_credentials(username, password)
        
        return True, "Учетные данные приняты."

    def try_auto_login(self):
        creds = self.load_credentials()
        if creds:
            self.current_user = creds['username']
            self.session.auth = HTTPBasicAuth(creds['username'], creds['password'])
            return True, "Данные загружены из кэша."
        return False, "Нет сохраненных данных."

    def is_network_ready(self):
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
        if progress_callback:
            progress_callback(f"Загрузка: {endpoint}...")
        
        url = f"{self.base_url}{endpoint}/"
        try:
            response = self.session.get(url, timeout=15)
            if response.status_code == 200:
                self.cache.save_data(endpoint, response.json())
                print(f"-> Кэш для '{endpoint}' обновлен.")
            else:
                print(f"-> Ошибка при запросе '{endpoint}': {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            print(f"-> Ошибка сети при синхронизации '{endpoint}': {e}")
            return False
        
        return True

    def get_local_data(self, endpoint):
        return self.cache.load_data(endpoint) or []

    def add_to_pending_queue(self, endpoint, data):
        """Добавляет запись в очередь ожидания отправки"""
        queue_key = f"pending_{endpoint}"
        pending_items = self.get_local_data(queue_key)
        pending_items.append(data)
        self.cache.save_data(queue_key, pending_items)
        print(f"-> Добавлено в очередь: {data.get('temp_id')}")

    def get_pending_count(self, endpoint):
        """Возвращает количество записей в очереди"""
        # ИСПРАВЛЕНО: используем get_pending_queue для консистентности
        return len(self.get_pending_queue(endpoint))

    def get_pending_queue(self, endpoint):
        """Возвращает очередь pending с проверкой структуры данных"""
        # ИСПРАВЛЕНО: endpoint уже без "pending_", мы его добавляем здесь
        if endpoint.startswith('pending_'):
            queue_key = endpoint  # Уже с префиксом
        else:
            queue_key = f"pending_{endpoint}"  # Добавляем префикс
        
        data = self.cache.load_data(queue_key)
        
        # Проверяем, что данные корректные
        if not isinstance(data, list):
            print(f"-> Некорректная структура {queue_key}, очищаем...")
            self.cache.save_data(queue_key, [])
            return []
        
        # Фильтруем только валидные записи
        valid_items = []
        for item in data:
            if isinstance(item, dict) and item.get('temp_id'):
                valid_items.append(item)
        
        # Если были невалидные записи, сохраняем только валидные
        if len(valid_items) != len(data):
            print(f"-> Найдено {len(data) - len(valid_items)} невалидных записей, удаляем...")
            self.cache.save_data(queue_key, valid_items)
        
        return valid_items



    def get_conflict_items(self):
        """Возвращает записи с конфликтами (желтые)"""
        return self.get_local_data('conflict_registries')

    def mark_as_conflict(self, item, reason):
        """Помечает запись как конфликтную"""
        conflicts = self.get_local_data('conflict_registries')
        item['conflict_reason'] = reason
        conflicts.append(item)
        self.cache.save_data('conflict_registries', conflicts)

    def remove_from_conflicts(self, temp_id):
        """Удаляет запись из конфликтов"""
        conflicts = self.get_local_data('conflict_registries')
        conflicts = [c for c in conflicts if c.get('temp_id') != temp_id]
        self.cache.save_data('conflict_registries', conflicts)

    def try_send_single_item(self, endpoint, temp_id):
        """Пытается отправить одну запись из очереди по ее temp_id (фоновая отправка)"""
        if not self.is_network_ready():
            print(f"Нет сети, отправка {temp_id} отложена.")
            return False

        queue_key = f"pending_{endpoint}"
        pending_items = self.get_local_data(queue_key)
        item_to_send = next((item for item in pending_items if item.get('temp_id') == temp_id), None)
        
        if not item_to_send:
            return False

        print(f"-> Фоновая отправка записи с temp_id: {temp_id}...")
        
        # Проверяем конфликты перед отправкой
        conflict = self.check_registry_conflict(item_to_send)
        if conflict:
            print(f" ...Обнаружен конфликт: {conflict}")
            self.mark_as_conflict(item_to_send, conflict)
            # Удаляем из очереди pending
            remaining = [item for item in pending_items if item.get('temp_id') != temp_id]
            self.cache.save_data(queue_key, remaining)
            
            # НОВОЕ: Уведомляем UI об обновлении
            if self.on_data_updated_callback:
                self.on_data_updated_callback()
            
            return False

        success, response_data, status_code = self.post_item(endpoint, item_to_send.copy())
        
        if success:
            # Проверяем, что сервер действительно создал запись
            if isinstance(response_data, dict) and response_data.get('id'):
                new_id = response_data.get('id')
                print(f" ...Успешно отправлено. Новый ID: {new_id}")
            elif isinstance(response_data, list) and len(response_data) > 0:
                new_id = response_data[0].get('id', 'unknown')
                print(f" ...Успешно отправлено. Новый ID: {new_id}")
            else:
                print(f" ...ОШИБКА: Неожиданный формат ответа: {type(response_data)}")
                return False
            
            # Удаляем из очереди pending
            remaining_items = [item for item in pending_items if item.get('temp_id') != temp_id]
            self.cache.save_data(queue_key, remaining_items)
            
            # Обновляем локальный кэш registries с сервера
            self.sync_endpoint('registries')
            
            # НОВОЕ: Уведомляем UI об обновлении
            if self.on_data_updated_callback:
                self.on_data_updated_callback()
            
            return True
        else:
            print(f" ...Ошибка фоновой отправки (статус {status_code}): {response_data}")
            return False

    def check_registry_conflict(self, local_item):
        """
        Проверяет конфликты с серверными данными.
        Возвращает строку с описанием конфликта или None.
        """
        # Получаем все записи с сервера
        server_items = self.get_local_data('registries') or []
        
        local_numberPL = str(local_item.get('numberPL', '')).strip()
        local_driver = local_item.get('driver')
        
        if not local_numberPL:
            return None  # Если номера ПЛ еще нет, конфликта быть не может
        
        # Ищем записи с таким же номером ПЛ на сервере
        for server_item in server_items:
            if not isinstance(server_item, dict):
                continue
                
            # Пропускаем записи без id (это локальные записи)
            if 'id' not in server_item:
                continue
                
            server_numberPL = str(server_item.get('numberPL', '')).strip()
            server_driver = server_item.get('driver')
            
            if server_numberPL == local_numberPL:
                # Номера ПЛ совпадают - проверяем водителя
                if local_driver != server_driver:
                    return f"Номер ПЛ {local_numberPL} уже существует с другим водителем"
        
        return None

    def post_item(self, endpoint, data):
        """Отправляет одну запись на сервер методом POST. Возвращает (success, response_data, status_code)"""
        url = f"{self.base_url}{endpoint}/"
        if not url.endswith('/'):
            url += '/'
        
        temp_id = data.pop('temp_id', None)
        data.pop('id', None)
        
        # Убираем пустые значения
        data = {k: v for k, v in data.items() if v not in [None, '', []]}
        
        print(f"--- Sending POST to {url} ---")
        print(json.dumps(data, indent=2, ensure_ascii=False))
        print("---------------------------------")
        
        try:
            # Отключаем автоматические редиректы
            response = self.session.post(
                url, 
                json=data, 
                timeout=15,
                headers={'Content-Type': 'application/json'},
                allow_redirects=False
            )
            
            # Проверяем, нет ли редиректа
            if response.status_code in [301, 302, 303, 307, 308]:
                print(f"-> РЕДИРЕКТ обнаружен: {response.status_code}")
                print(f"-> Location: {response.headers.get('Location')}")
                
                # Следуем редиректу вручную с POST методом
                redirect_url = response.headers.get('Location')
                if redirect_url:
                    if not redirect_url.startswith('http'):
                        redirect_url = self.base_url.rstrip('/') + redirect_url
                    
                    print(f"-> Повторный POST на: {redirect_url}")
                    response = self.session.post(
                        redirect_url,
                        json=data,
                        timeout=15,
                        headers={'Content-Type': 'application/json'}
                    )
            
            # Логируем детали ответа
            print(f"-> HTTP Status: {response.status_code}")
            print(f"-> Response Headers: {dict(response.headers)}")
            print(f"-> Request Method: {response.request.method}")
            
            # Для успешных ответов (2xx)
            if 200 <= response.status_code < 300:
                try:
                    response_json = response.json()
                    print(f"-> Response Body: {json.dumps(response_json, indent=2, ensure_ascii=False)}")
                    
                    if isinstance(response_json, list):
                        if len(response_json) == 0:
                            print("-> ОШИБКА: Пустой список. Возможные причины:")
                            print("   1. POST превратился в GET")
                            print("   2. Валидация не прошла")
                            print("   3. Проблема с сериализатором")
                            return False, "Validation error: empty response", response.status_code
                        else:
                            return True, response_json, response.status_code
                    else:
                        # Успешное создание объекта
                        return True, response_json, response.status_code
                        
                except ValueError:
                    print(f"-> Response Body (text): {response.text}")
                    return False, "Invalid JSON response", response.status_code
            else:
                # Для ошибок (4xx, 5xx)
                try:
                    error_body = response.json()
                    print(f"-> Error Body: {json.dumps(error_body, indent=2, ensure_ascii=False)}")
                    return False, error_body, response.status_code
                except:
                    print(f"-> Error Text: {response.text}")
                    return False, response.text, response.status_code
                
        except requests.exceptions.RequestException as e:
            error_details = str(e)
            status_code = None
            
            if hasattr(e, 'response') and e.response is not None:
                status_code = e.response.status_code
                try:
                    error_body = e.response.json()
                    error_details += f"\nServer error details: {json.dumps(error_body, indent=2, ensure_ascii=False)}"
                except:
                    error_details += f"\nServer response: {e.response.text}"
            
            if temp_id:
                data['temp_id'] = temp_id
            
            return False, error_details, status_code

    def upload_pending_registries(self, progress_callback=None):
        """
        Отправляет только записи из очереди pending_registries на сервер.
        Проверяет конфликты перед отправкой.
        """
        queue_key = "pending_registries"
        pending_items = self.get_pending_queue('registries')
        
        if not pending_items:
            print("-> Нет ожидающих записей для отправки.")
            if progress_callback:
                progress_callback("Нет записей для отправки")
            return 0, 0  # успешных, конфликтных
        
        if progress_callback:
            progress_callback(f"Отправка локальных записей: {len(pending_items)} шт...")
        
        success_count = 0
        conflict_count = 0
        remaining_items = []
        
        for item in pending_items:
            item_to_send = item.copy()
            temp_id = item_to_send.get('temp_id')
            
            print(f"-> Отправка записи с temp_id: {temp_id}...")
            
            # Проверяем конфликты
            conflict = self.check_registry_conflict(item_to_send)
            if conflict:
                print(f" ...Обнаружен конфликт: {conflict}")
                self.mark_as_conflict(item, conflict)
                conflict_count += 1
                continue
            
            success, response_data, status_code = self.post_item("registries", item_to_send)
            
            if success:
                # Проверяем, что данные действительно созданы
                if isinstance(response_data, dict) and response_data.get('id'):
                    new_id = response_data.get('id')
                    print(f" ...Успешно отправлено. Новый ID: {new_id}")
                    success_count += 1
                elif isinstance(response_data, list) and len(response_data) > 0:
                    new_id = response_data[0].get('id', 'unknown')
                    print(f" ...Успешно отправлено. Новый ID: {new_id}")
                    success_count += 1
                else:
                    print(f" ...ОШИБКА: Неожиданный формат ответа")
                    remaining_items.append(item)
            else:
                print(f" ...Ошибка отправки (статус {status_code}): {response_data}")
                remaining_items.append(item)
        
        self.cache.save_data(queue_key, remaining_items)
        print(f"-> Отправка завершена. Успешно: {success_count}, Конфликтов: {conflict_count}, Осталось в очереди: {len(remaining_items)}.")
        
        # Обновляем локальный кэш registries
        if success_count > 0:
            self.sync_endpoint('registries')
        
        return success_count, conflict_count

    def sync_pending_registries(self, progress_callback=None):
        """
        Полная синхронизация: отправка pending + загрузка с сервера.
        """
        # Сначала отправляем локальные изменения
        success_count, conflict_count = self.upload_pending_registries(progress_callback)
        
        # Затем загружаем обновленные данные с сервера
        if progress_callback:
            progress_callback("Загрузка обновленных данных с сервера...")
        
        self.sync_endpoint("registries", progress_callback)
        
        return success_count, conflict_count
