# api_client.py

import requests
from requests.auth import HTTPBasicAuth
from data_cache import LocalCache
import json
from urllib.parse import urlencode
import concurrent.futures

class APIClient:
    def __init__(self, base_url="https://agroup14.ru/api/v1/"):
        self.base_url = base_url
        self.session = requests.Session()
        self.cache = LocalCache()
        self.current_user = None
        self.current_user_id = None 
        self.on_data_updated_callback = None

    def set_data_updated_callback(self, callback):
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
            
            # Получение данных текущего пользователя
            self.current_user_id = None
            
            try:
                me_resp = self.session.get(f"{self.base_url}users/me/", timeout=10)
                if me_resp.status_code == 200:
                    me_data = me_resp.json()
                    if isinstance(me_data, dict) and me_data.get("id") is not None:
                        self.current_user_id = me_data["id"]
                        
                        # НОВОЕ: Сохраняем данные пользователя в кэш
                        self.cache.save_data('current_user_info', me_data)
                        # Сохраняем в список users (для совместимости с таблицей)
                        self.cache.save_data('users', [me_data])
                        
                        print(f"✓ User ID получен: {self.current_user_id}")
                        print(f"✓ Данные пользователя сохранены: {me_data.get('username')}")
            except Exception as e:
                print(f"✗ Ошибка получения /users/me/: {e}")
            
            if self.current_user_id is None:
                print("⚠ ВНИМАНИЕ: не удалось получить user_id, created_by будет None")
            else:
                print(f"✓ Авторизация успешна. User: {username}, ID: {self.current_user_id}")
        
        except requests.exceptions.RequestException as e:
            self.session.auth = None
            return False, f"Ошибка сети: {e}"
        
        if remember_me:
            self.save_credentials(username, password)
        
        return True, "Учетные данные приняты."


    def get_current_user_info(self):
        """Возвращает данные текущего пользователя из кэша"""
        return self.cache.load_data('current_user_info')


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
    
    def sync_current_user(self):
        """Синхронизирует данные текущего пользователя через /users/me/"""
        try:
            response = self.session.get(f"{self.base_url}users/me/", timeout=10)
            
            if response.status_code == 200:
                user_data = response.json()
                
                # Сохраняем данные текущего пользователя
                self.cache.save_data('current_user_info', user_data)
                
                # ВАЖНО: Создаем список из одного элемента для совместимости
                # с кодом, который ищет пользователей в списке
                self.cache.save_data('users', [user_data])
                
                print(f"✓ Данные текущего пользователя обновлены: {user_data.get('username')}")
                return True
            else:
                print(f"✗ Ошибка синхронизации пользователя: {response.status_code}")
                return False
        
        except Exception as e:
            print(f"✗ Ошибка синхронизации пользователя: {e}")
            return False

    def get_current_user_info(self):
        """Возвращает данные текущего пользователя из кэша"""
        return self.cache.load_data('current_user_info')


    def sync_all_parallel(self, endpoints, progress_callback=None, max_workers=5):
        """
        Синхронизирует несколько endpoints параллельно
        max_workers — количество одновременных запросов (по умолчанию 5)
        """
        if progress_callback:
            progress_callback(f"Параллельная синхронизация {len(endpoints)} источников...")
        
        results = {}
        
        def sync_one(endpoint):
            try:
                url = f"{self.base_url}{endpoint}/"
                response = self.session.get(url, timeout=10)  # Уменьшили timeout
                if response.status_code == 200:
                    self.cache.save_data(endpoint, response.json())
                    return endpoint, True, None
                else:
                    return endpoint, False, f"HTTP {response.status_code}"
            except Exception as e:
                return endpoint, False, str(e)
        
        # Используем ThreadPoolExecutor для параллельной загрузки
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_endpoint = {executor.submit(sync_one, ep): ep for ep in endpoints}
            
            completed = 0
            total = len(endpoints)
            
            for future in concurrent.futures.as_completed(future_to_endpoint):
                endpoint, success, error = future.result()
                completed += 1
                
                if progress_callback:
                    status = "✓" if success else "✗"
                    progress_callback(f"{status} {endpoint} ({completed}/{total})")
                
                if success:
                    print(f"-> Кэш для '{endpoint}' обновлен.")
                else:
                    print(f"-> Ошибка при запросе '{endpoint}': {error}")
                
                results[endpoint] = success
        
        return results

    def get_local_data(self, endpoint):
        return self.cache.load_data(endpoint) or []

    def add_to_pending_queue(self, endpoint, data):
        queue_key = f"pending_{endpoint}"
        pending_items = self.get_local_data(queue_key)
        pending_items.append(data)
        self.cache.save_data(queue_key, pending_items)
        print(f"-> Добавлено в очередь: {data.get('temp_id')}")

    def get_pending_count(self, endpoint):
        return len(self.get_pending_queue(endpoint))

    def get_pending_queue(self, endpoint):
        if endpoint.startswith('pending_'):
            queue_key = endpoint
        else:
            queue_key = f"pending_{endpoint}"
        data = self.cache.load_data(queue_key)
        if not isinstance(data, list):
            print(f"-> Некорректная структура {queue_key}, очищаем...")
            self.cache.save_data(queue_key, [])
            return []
        valid = [it for it in data if isinstance(it, dict) and it.get('temp_id')]
        if len(valid) != len(data):
            self.cache.save_data(queue_key, valid)
        return valid

    def get_conflict_items(self):
        return self.get_local_data('conflict_registries')

    def mark_as_conflict(self, item, reason):
        conflicts = self.get_local_data('conflict_registries')
        item['conflict_reason'] = reason
        conflicts.append(item)
        self.cache.save_data('conflict_registries', conflicts)

    def remove_from_conflicts(self, temp_id):
        conflicts = self.get_local_data('conflict_registries')
        conflicts = [c for c in conflicts if c.get('temp_id') != temp_id]
        self.cache.save_data('conflict_registries', conflicts)

    def try_send_single_item(self, endpoint, temp_id):
        """Пытается отправить один элемент из очереди"""
        if not self.is_network_ready():
            print(f"Нет сети, отправка {temp_id} отложена.")
            return False
        
        queue_key = f"pending_{endpoint}"
        pending_items = self.get_local_data(queue_key)
        
        item_to_send = next((item for item in pending_items if item.get('temp_id') == temp_id), None)
        
        if not item_to_send:
            return False
        
        print(f"-> Фоновая отправка записи с temp_id: {temp_id}...")
        
        # Проверка конфликтов
        conflict = self.check_registry_conflict(item_to_send)
        if conflict:
            print(f" ...Обнаружен конфликт: {conflict}")
            self.mark_as_conflict(item_to_send, conflict)
            
            # Удаляем из pending
            remaining = [item for item in pending_items if item.get('temp_id') != temp_id]
            self.cache.save_data(queue_key, remaining)
            
            if self.on_data_updated_callback:
                self.on_data_updated_callback()
            return False
        
        # Отправка на сервер
        success, response_data, status_code = self.post_item(endpoint, item_to_send.copy())
        
        if success:
            # ИСПРАВЛЕНО: Удаляем из pending после успешной отправки
            remaining_items = [item for item in pending_items if item.get('temp_id') != temp_id]
            self.cache.save_data(queue_key, remaining_items)
            
            # Синхронизируем реестр для получения серверного ID
            self.sync_endpoint('registries')
            
            if self.on_data_updated_callback:
                self.on_data_updated_callback()
            
            return True
        else:
            print(f" ...Ошибка фоновой отправки (статус {status_code}): {response_data}")
            return False


    def check_registry_conflict(self, local_item):
        server_items = self.get_local_data('registries') or []
        local_numberPL = str(local_item.get('numberPL', '')).strip()
        local_driver = local_item.get('driver')
        if not local_numberPL:
            return None
        for server_item in server_items:
            if not isinstance(server_item, dict) or 'id' not in server_item:
                continue
            if str(server_item.get('numberPL', '')).strip() == local_numberPL:
                if local_driver != server_item.get('driver'):
                    return f"Номер ПЛ {local_numberPL} уже существует с другим водителем"
        return None

    def post_item(self, endpoint, data):
        url = f"{self.base_url}{endpoint}/"
        if not url.endswith('/'):
            url += '/'
        temp_id = data.pop('temp_id', None)
        data.pop('id', None)

        # Добавляем пользователя при создании реестра
        if endpoint == "registries" and self.current_user_id is not None:
            data.setdefault("created_by", self.current_user_id)

        # Убираем пустые значения
        data = {k: v for k, v in data.items() if v not in [None, '', []]}
        print(f"--- Sending POST to {url} ---")
        print(json.dumps(data, indent=2, ensure_ascii=False))
        print("---------------------------------")
        try:
            response = self.session.post(
                url, json=data, timeout=15,
                headers={'Content-Type': 'application/json'},
                allow_redirects=False
            )
            if response.status_code in [301, 302, 303, 307, 308]:
                redirect_url = response.headers.get('Location')
                if redirect_url:
                    if not redirect_url.startswith('http'):
                        redirect_url = self.base_url.rstrip('/') + redirect_url
                    response = self.session.post(
                        redirect_url, json=data, timeout=15,
                        headers={'Content-Type': 'application/json'}
                    )
            print(f"-> HTTP Status: {response.status_code}")
            print(f"-> Request Method: {response.request.method}")
            if 200 <= response.status_code < 300:
                try:
                    body = response.json()
                    print(f"-> Response Body: {json.dumps(body, indent=2, ensure_ascii=False)}")
                    if isinstance(body, list) and len(body) == 0:
                        return False, "Validation error: empty response", response.status_code
                    return True, body, response.status_code
                except ValueError:
                    return False, "Invalid JSON response", response.status_code
            else:
                try:
                    err = response.json()
                except:
                    err = response.text
                return False, err, response.status_code
        except requests.exceptions.RequestException as e:
            status_code = getattr(getattr(e, 'response', None), 'status_code', None)
            details = str(e)
            if getattr(e, 'response', None) is not None:
                try:
                    details += f"\nServer error details: {json.dumps(e.response.json(), indent=2, ensure_ascii=False)}"
                except:
                    details += f"\nServer response: {e.response.text}"
            if temp_id:
                data['temp_id'] = temp_id
            return False, details, status_code

    def update_item(self, endpoint, item_id, data, use_patch=True):
        method = 'PATCH' if use_patch else 'PUT'
        url = f"{self.base_url}{endpoint}/{item_id}/"
        data = {k: v for k, v in data.items() if v not in [None, '', []]}
        print(f"--- {method} {url} ---")
        print(json.dumps(data, indent=2, ensure_ascii=False))
        print("---------------------------------")
        try:
            req = self.session.request(
                method=method,
                url=url,
                json=data,
                timeout=15,
                headers={'Content-Type': 'application/json'},
                allow_redirects=False
            )
            if req.status_code in [301, 302, 303, 307, 308]:
                redirect_url = req.headers.get('Location')
                if redirect_url:
                    if not redirect_url.startswith('http'):
                        redirect_url = self.base_url.rstrip('/') + redirect_url
                    req = self.session.request(
                        method=method,
                        url=redirect_url,
                        json=data,
                        timeout=15,
                        headers={'Content-Type': 'application/json'},
                    )
            print(f"-> HTTP Status: {req.status_code}")
            if 200 <= req.status_code < 300:
                try:
                    body = req.json()
                except ValueError:
                    body = req.text
                self.sync_endpoint('registries')
                if self.on_data_updated_callback:
                    self.on_data_updated_callback()
                return True, body, req.status_code
            else:
                try:
                    err = req.json()
                except:
                    err = req.text
                return False, err, req.status_code
        except requests.exceptions.RequestException as e:
            status_code = getattr(getattr(e, 'response', None), 'status_code', None)
            details = str(e)
            if getattr(e, 'response', None) is not None:
                try:
                    details += f"\nServer error details: {json.dumps(e.response.json(), indent=2, ensure_ascii=False)}"
                except:
                    details += f"\nServer response: {e.response.text}"
            return False, details, status_code

    # удаление одного объекта
    def delete_item(self, endpoint, item_id):
        url = f"{self.base_url}{endpoint}/{item_id}/"
        print(f"--- DELETE {url} ---")
        try:
            req = self.session.delete(url, timeout=15, allow_redirects=False)
            if req.status_code in [301, 302, 303, 307, 308]:
                redirect_url = req.headers.get('Location')
                if redirect_url:
                    if not redirect_url.startswith('http'):
                        redirect_url = self.base_url.rstrip('/') + redirect_url
                    req = self.session.delete(redirect_url, timeout=15)
            print(f"-> HTTP Status: {req.status_code}")
            if req.status_code in [200, 202, 204]:
                self.sync_endpoint('registries')
                if self.on_data_updated_callback:
                    self.on_data_updated_callback()
                return True, None, req.status_code
            else:
                try:
                    err = req.json()
                except:
                    err = req.text
                return False, err, req.status_code
        except requests.exceptions.RequestException as e:
            status_code = getattr(getattr(e, 'response', None), 'status_code', None)
            return False, str(e), status_code

    def upload_pending_registries(self, progress_callback=None):
        pending_items = self.get_pending_queue('registries')
        if not pending_items:
            print("-> Нет ожидающих записей для отправки.")
            if progress_callback:
                progress_callback("Нет записей для отправки")
            return 0, 0
        if progress_callback:
            progress_callback(f"Отправка локальных записей: {len(pending_items)} шт...")
        success_count, conflict_count = 0, 0
        remaining_items = []
        for item in pending_items:
            item_to_send = item.copy()
            temp_id = item_to_send.get('temp_id')
            conflict = self.check_registry_conflict(item_to_send)
            if conflict:
                print(f" ...Обнаружен конфликт: {conflict}")
                self.mark_as_conflict(item, conflict)
                conflict_count += 1
                continue
            ok, resp, code = self.post_item("registries", item_to_send)
            if ok:
                success_count += 1
            else:
                remaining_items.append(item)
        self.cache.save_data('pending_registries', remaining_items)
        if success_count > 0:
            self.sync_endpoint('registries')
        return success_count, conflict_count

    def sync_pending_registries(self, progress_callback=None):
        success_count, conflict_count = self.upload_pending_registries(progress_callback)
        if progress_callback:
            progress_callback("Загрузка обновленных данных с сервера...")
        self.sync_endpoint("registries", progress_callback)
        return success_count, conflict_count
