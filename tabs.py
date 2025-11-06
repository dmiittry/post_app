# tabs.py

import customtkinter as ctk
from tkinter import ttk, messagebox
from create_pl_form import CreatePLForm
from form_window import DataFormWindow
from settings_form import SettingsForm
import threading

class DataTable(ctk.CTkFrame):
    def __init__(self, master, api_client, endpoint, columns, sync_callback=None, upload_callback=None, can_edit=True):
        super().__init__(master, fg_color="transparent")
        
        self.api_client = api_client
        self.endpoint = endpoint
        self.columns_config = columns
        self.sync_callback = sync_callback
        self.upload_callback = upload_callback
        self.can_edit = can_edit
        self.all_data = []
        self.related_data = {}
        
        self._load_related_data()
        
        self.control_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.control_frame.pack(fill="x", pady=5)
        
        if self.endpoint == 'registries':
            if self.sync_callback:
                self.sync_button = ctk.CTkButton(
                    self.control_frame, 
                    text="Синхронизировать", 
                    command=self.sync_callback
                )
                self.sync_button.pack(side="left")
            
            if self.upload_callback:
                self.upload_button = ctk.CTkButton(
                    self.control_frame, 
                    text="Обновить данные", 
                    command=self.upload_callback,
                    fg_color="green"
                )
                self.upload_button.pack(side="left", padx=5)
        
        if self.can_edit:
            self.add_button = ctk.CTkButton(self.control_frame, text="Добавить", command=self.add_item)
            self.add_button.pack(side="left", padx=10)
        
        self.search_entry = ctk.CTkEntry(self.control_frame, placeholder_text="Поиск...")
        self.search_entry.pack(side="right", padx=5)
        self.search_entry.bind("<KeyRelease>", self.filter_data)
        
        # Стили для Treeview
        style = ttk.Style()
        style.configure("Treeview", background="#FFFFFF", foreground="#333333", 
                       fieldbackground="#FFFFFF", borderwidth=0)
        style.map('Treeview', background=[('selected', '#347083')])
        style.configure("Dark.Treeview", background="#2B2B2B", foreground="#DCE4EE", 
                       fieldbackground="#2B2B2B", borderwidth=0)
        style.map('Dark.Treeview', background=[('selected', '#347083')])
        
        tree_columns = ["#"] + list(self.columns_config.keys())
        
        self.tree = ttk.Treeview(
            self, 
            columns=tree_columns, 
            show='headings', 
            style="Dark.Treeview" if ctk.get_appearance_mode() == "Dark" else "Treeview"
        )
        
        self.tree.tag_configure('unsynced', foreground='red')
        self.tree.tag_configure('conflict', foreground='orange')
        
        self.sort_directions = {}
        
        self.tree.heading("#", text="#", command=lambda: self.sort_by_column("#", True))
        self.tree.column("#", width=50, anchor='center', stretch=False)
        
        for api_field, header_text in self.columns_config.items():
            self.tree.heading(api_field, text=header_text, 
                            command=lambda c=api_field: self.sort_by_column(c))
            self.tree.column(api_field, width=120, anchor='w')
        
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        
        self.tree.bind("<Double-1>", self.on_double_click)
        
        self.display_local_data()

    def _load_related_data(self):
        endpoints = ['seasons', 'organizations', 'customers', 'gruzes', 'cargo-batches', 
                    'drivers', 'cars', 'podryads', 'loading-points', 'unloading-points']
        for endpoint in endpoints:
            data = self.api_client.get_local_data(endpoint)
            # ИСПРАВЛЕНИЕ: проверяем, что данные - это список
            if isinstance(data, list):
                self.related_data[endpoint] = {
                    item.get('id'): item 
                    for item in data 
                    if isinstance(item, dict) and item.get('id') is not None
                }
            else:
                self.related_data[endpoint] = {}

    def reload_table_data(self):
        self._load_related_data()
        self.display_local_data()

    def display_local_data(self, data_source=None):
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        if self.endpoint == 'registries':
            # Загружаем данные с сервера
            server_data = self.api_client.get_local_data('registries')
            server_items = server_data if isinstance(server_data, list) else []
            
            # Загружаем pending (неотправленные)
            pending_data = self.api_client.get_local_data('pending_registries')
            pending_items = pending_data if isinstance(pending_data, list) else []
            
            # Загружаем конфликты
            conflict_data = self.api_client.get_local_data('conflict_registries')
            conflict_items = conflict_data if isinstance(conflict_data, list) else []
            
            # Объединяем все данные
            self.all_data = []
            
            # Добавляем серверные записи
            for item in server_items:
                if isinstance(item, dict):
                    self.all_data.append(item)
            
            # Добавляем pending записи (красные)
            for pending in pending_items:
                if isinstance(pending, dict):
                    # Проверяем, что эта запись еще не на сервере
                    if not any(isinstance(s, dict) and s.get('id') == pending.get('id') for s in server_items):
                        self.all_data.append(pending)
            
            # Добавляем конфликтные записи (желтые)
            for conflict in conflict_items:
                if isinstance(conflict, dict):
                    if not any(
                        isinstance(s, dict) and (
                            s.get('id') == conflict.get('id') or 
                            s.get('temp_id') == conflict.get('temp_id')
                        ) for s in self.all_data
                    ):
                        self.all_data.append(conflict)
            
            # Обновляем кнопки
            if hasattr(self, 'upload_button'):
                pending_count = len(pending_items)
                conflict_count = len(conflict_items)
                
                upload_text = "Обновить данные"
                if pending_count > 0 or conflict_count > 0:
                    upload_text += f" ({pending_count + conflict_count})"
                self.upload_button.configure(text=upload_text)
        else:
            raw_data = self.api_client.get_local_data(self.endpoint)
            self.all_data = [item for item in raw_data if isinstance(item, dict)] if isinstance(raw_data, list) else []
        
        data_to_display = data_source if data_source is not None else self.all_data
        
        # Получаем списки ID для определения статуса
        pending_data = self.api_client.get_local_data('pending_registries')
        pending_items = pending_data if isinstance(pending_data, list) else []
        pending_temp_ids = [p.get('temp_id') for p in pending_items if isinstance(p, dict)]
        
        conflict_data = self.api_client.get_local_data('conflict_registries')
        conflict_items = conflict_data if isinstance(conflict_data, list) else []
        conflict_temp_ids = [c.get('temp_id') for c in conflict_items if isinstance(c, dict)]
        
        for idx, item in enumerate(data_to_display, start=1):
            # ИСПРАВЛЕНИЕ: проверяем, что item - это словарь
            if not isinstance(item, dict):
                continue
            
            tags = ()
            
            if self.endpoint == 'registries':
                temp_id = item.get('temp_id')
                
                if temp_id in conflict_temp_ids:
                    tags = ('conflict',)
                elif temp_id in pending_temp_ids:
                    tags = ('unsynced',)
            
            row_values = [idx]
            
            for api_field in self.columns_config.keys():
                value = item.get(api_field)
                display_value = ""
                
                if value is not None:
                    lookup_key = ""
                    name_key = "name"
                    
                    if api_field == 'season':
                        lookup_key = 'seasons'
                    elif api_field == 'organization':
                        lookup_key = 'organizations'
                    elif api_field == 'customer':
                        lookup_key = 'customers'
                    elif api_field == 'gruz':
                        lookup_key = 'gruzes'
                    elif api_field == 'cargo_batch':
                        lookup_key = 'cargo-batches'
                        name_key = 'batch_number'
                    elif api_field in ['driver', 'driver2']:
                        lookup_key = 'drivers'
                        name_key = 'full_name'
                    elif api_field == 'number':
                        lookup_key = 'cars'
                        name_key = 'number'
                    elif api_field == 'pod':
                        lookup_key = 'podryads'
                        name_key = 'org_name'
                    elif api_field == 'loading_point':
                        lookup_key = 'loading-points'
                    elif api_field == 'unloading_point':
                        lookup_key = 'unloading-points'
                    
                    if lookup_key:
                        display_value = self.related_data.get(lookup_key, {}).get(value, {}).get(name_key, value)
                    else:
                        display_value = value
                
                row_values.append(display_value)
            
            item_id = item.get('id') or item.get('temp_id')
            
            if item_id and not self.tree.exists(item_id):
                self.tree.insert("", "end", values=row_values, iid=item_id, tags=tags)

    def sort_by_column(self, col, is_numeric=False):
        pass

    def filter_data(self, event):
        query = self.search_entry.get().lower()
        if not query:
            self.display_local_data()
            return
        
        filtered = []
        for item in self.all_data:
            # ИСПРАВЛЕНИЕ: проверяем, что item - это словарь
            if not isinstance(item, dict):
                continue
            
            for field in self.columns_config.keys():
                value = str(item.get(field, "")).lower()
                if query in value:
                    filtered.append(item)
                    break
        
        self.display_local_data(filtered)

    def add_item(self):
        if not self.can_edit:
            return
        DataFormWindow(
            master=self, 
            api_client=self.api_client, 
            endpoint=self.endpoint, 
            columns=self.columns_config, 
            on_save_callback=self.reload_table_data
        )

    def on_double_click(self, event):
        pass


class MainApplicationFrame(ctk.CTkFrame):
    def __init__(self, master, api_client, on_logout_callback, sync_callback):
        super().__init__(master, fg_color="transparent")
        
        self.api_client = api_client
        self.on_logout = on_logout_callback
        self.sync_callback = sync_callback
        
        self.tab_view = ctk.CTkTabview(self, anchor="w")
        self.tab_view.pack(fill="both", expand=True)
        
        self.tab_view.add("Реестр")
        self.tab_view.add("Создать ПЛ")
        self.tab_view.add("Водители")
        self.tab_view.add("Подрядчики")
        self.tab_view.add("Настройки")
        
        self.create_registry_tab(self.tab_view.tab("Реестр"))
        self.create_pl_creation_tab(self.tab_view.tab("Создать ПЛ"))
        self.create_drivers_tab(self.tab_view.tab("Водители"))
        self.create_contractors_tab(self.tab_view.tab("Подрядчики"))
        self.create_settings_tab(self.tab_view.tab("Настройки"))
        
        self.logout_button = ctk.CTkButton(
            self.tab_view.tab("Настройки"), 
            text="Выйти", 
            command=self.handle_logout, 
            width=200
        )
        self.logout_button.pack(side='bottom', pady=50)

    def create_registry_tab(self, tab):
        columns = {
            "season": "Сезон", "organization": "Организация", "customer": "Заказчик", "gruz": "Груз",
            "cargo_batch": "Партия", "driver": "Водитель", "driver2": "2-й Водитель", "number": "ТС",
            "pod": "Подрядчик", "loading_point": "Погрузка", "unloading_point": "Разгрузка", "marsh": "Маршрут",
            "distance": "Дист.", "numberPL": "№ ПЛ", "dataPOPL": "Дата выдачи", "dataSDPL": "Дата сдачи",
            "numberTN": "№ ТТН", "loading_time": "Время погр.", "unloading_time": "Время разгр.", "tonn": "Тоннаж",
            "fuel_consumption": "ГСМ", "dispatch_info": "Инфо", "comment": "Комментарий",
        }
        
        self.registry_table = DataTable(
            tab, 
            self.api_client, 
            'registries', 
            columns, 
            sync_callback=self.sync_callback,
            upload_callback=self.upload_pending
        )
        self.registry_table.pack(fill="both", expand=True)

    def upload_pending(self):
        """Отправляет только pending записи на сервер"""
        if not self.api_client.is_network_ready():
            messagebox.showerror("Ошибка", "Нет подключения к серверу")
            return
        
        pending_count = self.api_client.get_pending_count('registries')
        conflict_items = self.api_client.get_conflict_items()
        conflict_count = len(conflict_items) if isinstance(conflict_items, list) else 0
        
        if pending_count == 0 and conflict_count == 0:
            messagebox.showinfo("Информация", "Нет данных для отправки")
            return
        
        def upload_worker():
            try:
                success, conflicts = self.api_client.upload_pending_registries()
                
                # Обновляем таблицу в главном потоке
                self.after(0, self.reload_registry_table)
                
                msg = f"Отправлено успешно: {success}\n"
                if conflicts > 0:
                    msg += f"Обнаружено конфликтов: {conflicts}\n(показаны желтым цветом)"
                
                self.after(0, lambda: messagebox.showinfo("Результат отправки", msg))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Ошибка", f"Ошибка отправки: {e}"))
        
        threading.Thread(target=upload_worker, daemon=True).start()

    def create_pl_creation_tab(self, tab):
        self.pl_form = CreatePLForm(tab, self.api_client, on_save_callback=self.reload_registry_table)
        self.pl_form.pack(fill="both", expand=True)

    def reload_pl_creation_tab(self):
        """Перезагружает форму создания ПЛ после изменения настроек"""
        if hasattr(self, 'pl_form') and self.pl_form.winfo_exists():
            # Если форма уже существует, просто обновляем настройки
            self.pl_form.reload_settings()
        else:
            # Иначе создаем заново
            self.pl_form = CreatePLForm(
                self.tab_view.tab("Создать ПЛ"), 
                self.api_client, 
                on_save_callback=self.reload_registry_table
            )
            self.pl_form.pack(fill="both", expand=True)

    def reload_registry_table(self):
        if hasattr(self, 'registry_table'):
            self.registry_table.reload_table_data()
            self.tab_view.set("Реестр")

    def create_drivers_tab(self, tab):
        columns = {'full_name': 'ФИО', 'birth_date': 'Дата рождения', 'phone_1': 'Телефон', 'status': 'Статус'}
        DataTable(tab, self.api_client, 'drivers', columns, can_edit=False).pack(fill="both", expand=True)

    def create_contractors_tab(self, tab):
        columns = {'org_name': 'Название', 'full_name': 'Руководитель', 'inn': 'ИНН'}
        DataTable(tab, self.api_client, 'podryads', columns, can_edit=False).pack(fill="both", expand=True)

    def create_settings_tab(self, tab):
        self.settings_frame = SettingsForm(tab, self.api_client, on_save_callback=self.reload_pl_creation_tab)
        self.settings_frame.pack(fill="both", expand=True, padx=20, pady=20)

    def handle_logout(self):
        self.api_client.logout()
        self.on_logout()

    def reload_all_tables(self):
        self.reload_pl_creation_tab()
        
        if hasattr(self, 'settings_frame') and self.settings_frame.winfo_exists():
            self.settings_frame.destroy()
        self.create_settings_tab(self.tab_view.tab("Настройки"))
        
        for tab_name in self.tab_view._name_list:
            tab_frame = self.tab_view.tab(tab_name)
            if tab_frame.winfo_children() and isinstance(tab_frame.winfo_children()[0], DataTable):
                tab_frame.winfo_children()[0].reload_table_data()
