# tabs.py

import customtkinter as ctk
from tkinter import ttk, messagebox
from tkcalendar import DateEntry
from create_pl_form import CreatePLForm
from form_window import DataFormWindow
from settings_form import SettingsForm
from registry_card import RegistryCardWindow
import threading
from datetime import datetime


def format_datetime(iso_str):
    """Форматирует ISO datetime в 'ДД.ММ.ГГГГ ЧЧ:ММ'"""
    if not iso_str:
        return ""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00")) if "Z" in iso_str else datetime.fromisoformat(iso_str)
        return dt.strftime("%d.%m.%Y %H:%M")
    except:
        return str(iso_str)


class DataTable(ctk.CTkFrame):
    def __init__(self, master, api_client, endpoint, columns, sync_callback=None, upload_callback=None, can_edit=True, column_widths=None):
        super().__init__(master, fg_color="transparent")

        self.api_client = api_client
        self.endpoint = endpoint
        self.columns_config = columns
        self.column_widths = column_widths or {} 
        self.sync_callback = sync_callback
        self.upload_callback = upload_callback
        self.can_edit = can_edit
        self.all_data = []
        self.related_data = {}
        self.filters = {
            "query": "",
            "season": None,
            "gruz": None,
            "marsh": "",
            "dispatch": "",
            "decade_from_date": None,
            "decade_from_hour": 0,
            "decade_from_min": 0,
            "decade_to_date": None,
            "decade_to_hour": 23,
            "decade_to_min": 59,
        }
        self.season_name_to_id = {}
        self.gruz_name_to_id = {}

        self._load_related_data()

        # Верхняя панель управления
        self.control_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.control_frame.pack(fill="x", pady=(6, 4))

        if self.endpoint == 'registries':
            if self.sync_callback:
                self.sync_button = ctk.CTkButton(self.control_frame, text="Синхронизировать", command=self.sync_callback)
                self.sync_button.pack(side="left", padx=(0, 6))
            if self.upload_callback:
                self.upload_button = ctk.CTkButton(self.control_frame, text="Обновить данные", command=self.upload_callback, fg_color="green")
                self.upload_button.pack(side="left", padx=(0, 6))

            # Действия над выделенными
            self.actions_button = ctk.CTkButton(self.control_frame, text="Отправка (выдел.)", command=self.open_dispatch_dialog)
            self.actions_button.pack(side="left", padx=(0, 6))

            self.received_button = ctk.CTkButton(self.control_frame, text="Сдали документы (выдел.)", command=self.mark_selected_received, fg_color="#2e7d32")
            self.received_button.pack(side="left", padx=(0, 6))

        if self.can_edit and self.endpoint != 'registries':
            self.add_button = ctk.CTkButton(self.control_frame, text="Добавить", command=self.add_item)
            self.add_button.pack(side="left", padx=(6, 6))

        # Панель фильтров
        self.filters_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.filters_frame.pack(fill="x", pady=(0, 6))

        # Общий поиск (зависит от endpoint)
        if self.endpoint == 'registries':
            placeholder = "Поиск: ФИО водителей, № ТС, подрядчик, № ПЛ..."
        elif self.endpoint == 'drivers':
            placeholder = "Поиск: ФИО, № ТС, телефон..."
        elif self.endpoint == 'podryads':
            placeholder = "Поиск: ФИО директора, название, телефон..."
        else:
            placeholder = "Поиск..."

        # ИСПРАВЛЕНО: убран лишний padx справа
        self.search_entry = ctk.CTkEntry(self.filters_frame, placeholder_text=placeholder, width=300)
        self.search_entry.pack(side="right", padx=(6, 6))
        self.search_entry.bind("<KeyRelease>", self.on_query_change)

        if self.endpoint == 'registries':
            # Фильтр по отправке
            self.dispatch_entry = ctk.CTkEntry(self.filters_frame, placeholder_text="Фильтр по отправке", width=180)
            self.dispatch_entry.pack(side="right", padx=(6, 0))
            self.dispatch_entry.bind("<KeyRelease>", self.on_dispatch_change)

            # Фильтр по маршруту
            self.marsh_entry = ctk.CTkEntry(self.filters_frame, placeholder_text="Фильтр по маршруту", width=140)
            self.marsh_entry.pack(side="right", padx=(6, 0))
            self.marsh_entry.bind("<KeyRelease>", self.on_marsh_change)

            # Фильтр по грузу
            gruz_names = ["— все —"] + [g.get('name', '') for g in self.api_client.get_local_data('gruzes') if isinstance(g, dict)]
            self.gruz_combo = ctk.CTkComboBox(self.filters_frame, values=gruz_names, state="readonly", command=self.on_gruz_change, width=140)
            self.gruz_combo.set("— все —")
            self.gruz_combo.pack(side="right", padx=(6, 0))

            # Фильтр по сезону
            season_names = ["— все —"] + [s.get('name', '') for s in self.api_client.get_local_data('seasons') if isinstance(s, dict)]
            self.season_combo = ctk.CTkComboBox(self.filters_frame, values=season_names, state="readonly", command=self.on_season_change, width=140)
            self.season_combo.set("— все —")
            self.season_combo.pack(side="right", padx=(6, 0))

            # Фильтр «Декада» (период разгрузки с учетом времени)
            # ctk.CTkLabel(self.filters_frame, text="Декада (разгрузка):").pack(side="right", padx=(6, 2))
            
            # От: дата + время
            # decade_from_frame = ctk.CTkFrame(self.filters_frame, fg_color="transparent")
            # decade_from_frame.pack(side="right", padx=(2, 0))
            # self.decade_from_date = DateEntry(decade_from_frame, date_pattern='dd.mm.yyyy', width=10)
            # self.decade_from_date.pack(side="left")
            # self.decade_from_hour = ctk.CTkComboBox(decade_from_frame, values=[f"{h:02d}" for h in range(24)], width=50, command=lambda _: self.on_decade_change())
            # self.decade_from_hour.set("00")
            # self.decade_from_hour.pack(side="left", padx=2)
            # self.decade_from_min = ctk.CTkComboBox(decade_from_frame, values=[f"{m:02d}" for m in range(0, 60, 5)], width=50, command=lambda _: self.on_decade_change())
            # self.decade_from_min.set("00")
            # self.decade_from_min.pack(side="left")
            # self.decade_from_date.bind("<<DateEntrySelected>>", self.on_decade_change)

            # ctk.CTkLabel(self.filters_frame, text="–").pack(side="right", padx=2)

            # # До: дата + время
            # decade_to_frame = ctk.CTkFrame(self.filters_frame, fg_color="transparent")
            # decade_to_frame.pack(side="right", padx=(0, 2))
            # self.decade_to_date = DateEntry(decade_to_frame, date_pattern='dd.mm.yyyy', width=10)
            # self.decade_to_date.pack(side="left")
            # self.decade_to_hour = ctk.CTkComboBox(decade_to_frame, values=[f"{h:02d}" for h in range(24)], width=50, command=lambda _: self.on_decade_change())
            # self.decade_to_hour.set("23")
            # self.decade_to_hour.pack(side="left", padx=2)
            # self.decade_to_min = ctk.CTkComboBox(decade_to_frame, values=[f"{m:02d}" for m in range(0, 60, 5)], width=50, command=lambda _: self.on_decade_change())
            # self.decade_to_min.set("55")
            # self.decade_to_min.pack(side="left")
            # self.decade_to_date.bind("<<DateEntrySelected>>", self.on_decade_change)

            # self.reset_filters_btn = ctk.CTkButton(self.filters_frame, text="Сбросить фильтры", command=self.reset_filters, width=130)
            # self.reset_filters_btn.pack(side="right", padx=(0, 6))

        # Таблица
        style = ttk.Style()
        style.configure("Treeview", background="#FFFFFF", foreground="#333333", fieldbackground="#FFFFFF", borderwidth=0)
        style.map('Treeview', background=[('selected', '#347083')])
        style.configure("Dark.Treeview", background="#2B2B2B", foreground="#DCE4EE", fieldbackground="#2B2B2B", borderwidth=0)
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
        # Полученные документы — тёмно‑зелёный с белым текстом
        self.tree.tag_configure('received', background='#2e7d32', foreground='#ffffff')
        # Отправленные — тёмно‑синий с белым текстом
        self.tree.tag_configure('dispatched', background='#1565c0', foreground='#ffffff')

        self.sort_directions = {}

        self.tree.heading("#", text="#", command=lambda: self.sort_by_column("#", True))
        width_num = self.column_widths.get("#", 50)
        self.tree.column("#", width=width_num, anchor='center', stretch=False)

        for api_field, header_text in self.columns_config.items():
            self.tree.heading(api_field, text=header_text, command=lambda c=api_field: self.sort_by_column(c))
            width = self.column_widths.get(api_field, 130)
            self.tree.column(api_field, width=width, anchor='w')

        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)

        self.tree.bind("<Double-1>", self.on_double_click)

        self.display_local_data()

    def _load_related_data(self):
        endpoints = ['drivers', 'cars', 'podryads', 'gruzes', 'seasons', 'car-markas', 'car-models']
        for endpoint in endpoints:
            self.related_data[endpoint] = {
                item.get('id'): item
                for item in self.api_client.get_local_data(endpoint)
                if isinstance(item, dict) and item.get('id') is not None
            }
        self.season_name_to_id = {v.get('name', ''): k for k, v in self.related_data.get('seasons', {}).items()}
        self.gruz_name_to_id = {v.get('name', ''): k for k, v in self.related_data.get('gruzes', {}).items()}

    def reload_table_data(self):
        self._load_related_data()
        self.display_local_data()

    def _apply_filters(self, items):
        q = (self.filters.get("query") or "").lower()
        season_id = self.filters.get("season")
        gruz_id = self.filters.get("gruz")
        marsh_q = (self.filters.get("marsh") or "").lower()
        dispatch_q = (self.filters.get("dispatch") or "").lower()

        # Декада с учетом времени
        decade_from_date = self.filters.get("decade_from_date")
        decade_from_hour = self.filters.get("decade_from_hour", 0)
        decade_from_min = self.filters.get("decade_from_min", 0)
        decade_to_date = self.filters.get("decade_to_date")
        decade_to_hour = self.filters.get("decade_to_hour", 23)
        decade_to_min = self.filters.get("decade_to_min", 59)

        def match(item: dict):
            if self.endpoint == 'registries':
                if season_id and item.get('season') != season_id:
                    return False
                if gruz_id and item.get('gruz') != gruz_id:
                    return False
                if marsh_q:
                    if marsh_q not in str(item.get('marsh', '')).lower():
                        return False
                if dispatch_q:
                    if dispatch_q not in str(item.get('dispatch_info', '')).lower():
                        return False

                # Декада по unloading_time с учетом времени
                if decade_from_date or decade_to_date:
                    unload = item.get('unloading_time')
                    if unload:
                        try:
                            # Парсим и сразу убираем timezone
                            if isinstance(unload, str):
                                # Убираем timezone из строки: 2025-11-07T22:00:00+09:00 -> 2025-11-07T22:00:00
                                unload_clean = unload.split('+')[0].split('Z')[0]
                                dt = datetime.fromisoformat(unload_clean)
                            else:
                                dt = None
                        except Exception as e:
                            print(f"Ошибка парсинга unloading_time: {unload}, error: {e}")
                            dt = None
                        
                        if dt:
                            if decade_from_date:
                                from_dt = datetime.combine(decade_from_date, datetime.min.time()).replace(hour=decade_from_hour, minute=decade_from_min)
                                if dt < from_dt:
                                    return False
                            if decade_to_date:
                                to_dt = datetime.combine(decade_to_date, datetime.min.time()).replace(hour=decade_to_hour, minute=decade_to_min)
                                if dt > to_dt:
                                    return False
                        else:
                            return False
                    else:
                        return False

                # Общий поиск
                if q:
                    d1_name = self.related_data.get('drivers', {}).get(item.get('driver'), {}).get('full_name', '')
                    d2_name = self.related_data.get('drivers', {}).get(item.get('driver2'), {}).get('full_name', '')
                    car_num = self.related_data.get('cars', {}).get(item.get('number'), {}).get('number', '')
                    pod_name = self.related_data.get('podryads', {}).get(item.get('pod'), {}).get('org_name', '')
                    number_pl = str(item.get('numberPL', ''))
                    haystack = " ".join([d1_name, d2_name, car_num, pod_name, number_pl]).lower()
                    if q not in haystack:
                        return False

            elif self.endpoint == 'drivers':
                if q:
                    fname = str(item.get('full_name', '')).lower()
                    phone1 = str(item.get('phone_1', '')).lower()
                    phone2 = str(item.get('phone_2', '')).lower()
                    phone3 = str(item.get('phone_3', '')).lower()
                    car_ids = item.get('cars') or []
                    car_nums = []
                    for cid in car_ids:
                        c = self.related_data.get('cars', {}).get(cid)
                        if c:
                            car_nums.append(str(c.get('number', '')).lower())
                    haystack = " ".join([fname, phone1, phone2, phone3] + car_nums)
                    if q not in haystack:
                        return False

            elif self.endpoint == 'podryads':
                if q:
                    org_name = str(item.get('org_name', '')).lower()
                    full_name = str(item.get('full_name', '')).lower()
                    phone = str(item.get('phone_1', '')).lower()
                    haystack = " ".join([org_name, full_name, phone])
                    if q not in haystack:
                        return False

            return True

        return [it for it in items if isinstance(it, dict) and match(it)]


    def display_local_data(self, data_source=None):
        for item in self.tree.get_children():
            self.tree.delete(item)

        if self.endpoint == 'registries':
            server_items = self.api_client.get_local_data('registries') or []
            pending_items = self.api_client.get_local_data('pending_registries') or []
            conflict_items = self.api_client.get_local_data('conflict_registries') or []
            merged = [s for s in server_items if isinstance(s, dict)]

            for p in pending_items:
                if isinstance(p, dict):
                    if not any(isinstance(s, dict) and s.get('id') == p.get('id') for s in server_items):
                        merged.append(p)
            for c in conflict_items:
                if isinstance(c, dict):
                    if not any(isinstance(s, dict) and (s.get('id') == c.get('id') or s.get('temp_id') == c.get('temp_id')) for s in merged):
                        merged.append(c)
            #Сортируем по ID (по убыванию — новые сверху)
            merged.sort(key=lambda x: x.get('id') or 0, reverse=True)

            self.all_data = merged
            if hasattr(self, 'upload_button'):
                pending_count = len([p for p in pending_items if isinstance(p, dict)])
                conflict_count = len([c for c in conflict_items if isinstance(c, dict)])
                text = "Обновить данные"
                if pending_count + conflict_count > 0:
                    text += f" ({pending_count + conflict_count})"
                self.upload_button.configure(text=text)
        else:
            raw = self.api_client.get_local_data(self.endpoint)
            self.all_data = [it for it in raw if isinstance(it, dict)]

        source = data_source if data_source is not None else self.all_data
        data_to_display = self._apply_filters(source)

        pending_temp_ids = [p.get('temp_id') for p in (self.api_client.get_local_data('pending_registries') or []) if isinstance(p, dict)]
        conflict_temp_ids = [c.get('temp_id') for c in (self.api_client.get_local_data('conflict_registries') or []) if isinstance(c, dict)]

        #обратная нумерация
        total_count = len(data_to_display)

        for idx, item in enumerate(data_to_display, start=1):
            if not isinstance(item, dict):
                continue
            
            reverse_idx = total_count - idx + 1
            tags = []
            if self.endpoint == 'registries':
                temp_id = item.get('temp_id')
                if temp_id in conflict_temp_ids:
                    tags.append('conflict')
                elif temp_id in pending_temp_ids:
                    tags.append('unsynced')

                # Исправлено: подсветка только по реальному состоянию отправки/получения            
                dispatch_raw = item.get('dispatch_info', '')
                dispatch = str(dispatch_raw or '').strip().lower()
                if dispatch:
                    # Зеленый: если явно содержит «получил»/«получили»
                    if 'получил' in dispatch:
                        tags.append('received')
                    else:
                        # Синий: любая другая непустая отправка
                        tags.append('dispatched')
                # Пустое dispatch_info — без цветового тега

            row_values = [reverse_idx]
            for api_field in self.columns_config.keys():
                value = item.get(api_field)
                display_value = ""
                if value is not None:
                    # форматируем все datetime поля
                    if api_field == 'created_by':
                        # value — это user_id, нужно получить username
                        users = self.api_client.get_local_data('users') or []
                        user = next((u for u in users if u.get('id') == value), None)
                        display_value = user.get('username', str(value)) if user else str(value)
                    elif api_field in ['dataPOPL', 'dataSDPL', 'loading_time', 'unloading_time', 'approved_at']:
                        display_value = format_datetime(value)
                    elif api_field in ['driver', 'driver2']:
                        display_value = self.related_data.get('drivers', {}).get(value, {}).get('full_name', value)
                    elif api_field == 'number':
                        display_value = self.related_data.get('cars', {}).get(value, {}).get('number', value)
                    elif api_field == 'pod' or api_field == 'contractor':
                        display_value = self.related_data.get('podryads', {}).get(value, {}).get('org_name', value)
                    elif api_field == 'gruz':
                        display_value = self.related_data.get('gruzes', {}).get(value, {}).get('name', value)
                    elif api_field == 'marka':
                        display_value = self.related_data.get('car-markas', {}).get(value, {}).get('name', value)
                    elif api_field == 'model':
                        display_value = self.related_data.get('car-models', {}).get(value, {}).get('name', value)
                    elif api_field == 'status':
                        # Преобразуем английские статусы в русский текст
                        status_map = {
                            'draft': 'Черновик',
                            'pending': 'На рассмотрении',
                            'approved': 'Одобрено',
                            'rejected': 'Отклонено',
                            'active': 'Активен',
                            'inactive': 'Неактивен',
                        }
                        display_value = status_map.get(str(value).lower(), value)
                    elif api_field == 'cars':
                        # Список ТС (для водителей)
                        if isinstance(value, list):
                            car_nums = []
                            for cid in value:
                                c = self.related_data.get('cars', {}).get(cid)
                                if c:
                                    car_nums.append(c.get('number', ''))
                            display_value = ', '.join(car_nums)
                        else:
                            display_value = value
                    else:
                        display_value = value
                row_values.append(display_value)

            item_id = item.get('id') or item.get('temp_id')
            iid_str = str(item_id) if item_id is not None else str(idx)
            if not self.tree.exists(iid_str):
                self.tree.insert("", "end", values=row_values, iid=iid_str, tags=tuple(tags))

    def mark_selected_received(self):
        if self.endpoint != 'registries':
            return
        sel = self._get_selected_records()
        if not sel:
            from tkinter import messagebox
            messagebox.showinfo("Информация", "Выберите записи в таблице.")
            return

        # Блокируем кнопку на время операции
        btn = getattr(self, 'received_button', None)
        if btn and btn.winfo_exists():
            btn.configure(state="disabled")

        from datetime import datetime
        now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

        def worker():
            ok_cnt, err_cnt, skip_cnt = 0, 0, 0
            for rec in sel:
                rec_id = rec.get('id')
                if not rec_id:
                    skip_cnt += 1
                    continue
                payload = {"dispatch_info": "получили", "dataSDPL": now}
                ok, resp, code = self.api_client.update_item('registries', rec_id, payload, use_patch=True)
                if ok:
                    ok_cnt += 1
                else:
                    err_cnt += 1

            def done():
                # Вернуть кнопку
                if btn and btn.winfo_exists():
                    btn.configure(state="normal")
                # Обновить таблицу и показать результат
                if self.winfo_exists():
                    self.reload_table_data()
                    from tkinter import messagebox
                    messagebox.showinfo("Готово", f"Отмечено «Сдали документы»: {ok_cnt}\nПропущено: {skip_cnt}\nОшибок: {err_cnt}")
            self.after(0, done)

        import threading
        threading.Thread(target=worker, daemon=True).start()    

    def sort_by_column(self, col, is_numeric=False):
        pass

    # ----- Поиск/фильтры -----
    def on_query_change(self, event):
        self.filters['query'] = self.search_entry.get().strip()
        self.display_local_data()

    def on_marsh_change(self, event):
        self.filters['marsh'] = self.marsh_entry.get().strip()
        self.display_local_data()

    def on_dispatch_change(self, event):
        self.filters['dispatch'] = self.dispatch_entry.get().strip()
        self.display_local_data()

    def on_decade_change(self, event=None):
        try:
            self.filters['decade_from_date'] = self.decade_from_date.get_date()
            self.filters['decade_from_hour'] = int(self.decade_from_hour.get())
            self.filters['decade_from_min'] = int(self.decade_from_min.get())
        except:
            self.filters['decade_from_date'] = None
            self.filters['decade_from_hour'] = 0
            self.filters['decade_from_min'] = 0
        try:
            self.filters['decade_to_date'] = self.decade_to_date.get_date()
            self.filters['decade_to_hour'] = int(self.decade_to_hour.get())
            self.filters['decade_to_min'] = int(self.decade_to_min.get())
        except:
            self.filters['decade_to_date'] = None
            self.filters['decade_to_hour'] = 23
            self.filters['decade_to_min'] = 59
        self.display_local_data()

    def on_season_change(self, selected: str):
        if selected and selected != "— все —":
            self.filters['season'] = self.season_name_to_id.get(selected)
        else:
            self.filters['season'] = None
        self.display_local_data()

    def on_gruz_change(self, selected: str):
        if selected and selected != "— все —":
            self.filters['gruz'] = self.gruz_name_to_id.get(selected)
        else:
            self.filters['gruz'] = None
        self.display_local_data()

    def reset_filters(self):
        self.filters = {
            "query": "", "season": None, "gruz": None, "marsh": "", "dispatch": "",
            "decade_from_date": None, "decade_from_hour": 0, "decade_from_min": 0,
            "decade_to_date": None, "decade_to_hour": 23, "decade_to_min": 59
        }
        self.search_entry.delete(0, "end")
        if hasattr(self, 'marsh_entry'):
            self.marsh_entry.delete(0, "end")
        if hasattr(self, 'dispatch_entry'):
            self.dispatch_entry.delete(0, "end")
        if hasattr(self, 'season_combo'):
            self.season_combo.set("— все —")
        if hasattr(self, 'gruz_combo'):
            self.gruz_combo.set("— все —")
        if hasattr(self, 'decade_from_date'):
            self.decade_from_date.set_date(datetime.now())
            self.decade_from_hour.set("00")
            self.decade_from_min.set("00")
        if hasattr(self, 'decade_to_date'):
            self.decade_to_date.set_date(datetime.now())
            self.decade_to_hour.set("23")
            self.decade_to_min.set("55")
        self.display_local_data()

    def filter_data(self, event):
        self.on_query_change(event)

    def add_item(self):
        if not self.can_edit:
            return
        DataFormWindow(self, self.api_client, self.endpoint, self.columns_config, on_save_callback=self.reload_table_data)

    def on_double_click(self, event):
        if self.endpoint != 'registries':
            return
        iid = self.tree.identify_row(event.y)
        if not iid:
            sel = self.tree.selection()
            if not sel:
                return
            iid = sel[0]
        rec = None
        for it in self.all_data:
            if not isinstance(it, dict):
                continue
            item_id = it.get('id') or it.get('temp_id')
            if str(item_id) == str(iid):
                rec = it
                break
        if not rec:
            return
        RegistryCardWindow(self, self.api_client, rec, on_saved_callback=self.reload_table_data)

    # ----- Массовые действия -----
    def _get_selected_records(self):
        iids = self.tree.selection()
        selected = []
        for iid in iids:
            for it in self.all_data:
                if not isinstance(it, dict):
                    continue
                item_id = it.get('id') or it.get('temp_id')
                if str(item_id) == str(iid):
                    selected.append(it)
                    break
        return selected

    def open_dispatch_dialog(self):
        if self.endpoint != 'registries':
            return
        sel = self._get_selected_records()
        if not sel:
            messagebox.showinfo("Информация", "Выберите записи в таблице.")
            return

        dlg = ctk.CTkToplevel(self)
        dlg.title("Отправка")
        dlg.geometry("420x200")
        dlg.transient(self)
        dlg.grab_set()

        ctk.CTkLabel(dlg, text="Введите текст отправки:").pack(pady=(10, 6))
        entry = ctk.CTkEntry(dlg, width=360)
        entry.pack(pady=(0, 10))
        status = ctk.CTkLabel(dlg, text="", anchor="w")
        status.pack(fill="x", padx=10)

        btn_frame = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_frame.pack(fill="x", pady=10)
        btn_ok = ctk.CTkButton(btn_frame, text="Применить")
        btn_ok.pack(side="left", padx=8)
        btn_cancel = ctk.CTkButton(btn_frame, text="Отмена", fg_color="#616161", command=lambda: (dlg.destroy() if dlg.winfo_exists() else None))
        btn_cancel.pack(side="left")

        def set_status(txt):
            if dlg.winfo_exists():
                status.configure(text=txt)

        def on_apply():
            # Защита от двойного клика
            btn_ok.configure(state="disabled")
            text = entry.get().strip()

            def worker():
                ok_cnt = 0
                err_cnt = 0
                for rec in sel:
                    rec_id = rec.get('id')
                    if not rec_id:
                        continue
                    ok, resp, code = self.api_client.update_item('registries', rec_id, {"dispatch_info": text}, use_patch=True)
                    if ok: ok_cnt += 1
                    else: err_cnt += 1

                def done():
                    # Обновляем таблицу
                    if self.winfo_exists():
                        self.reload_table_data()
                    # Сообщение и закрытие только если окно живо
                    if dlg.winfo_exists():
                        messagebox.showinfo("Готово", f"Обновлено: {ok_cnt}\nОшибок: {err_cnt}")
                        dlg.destroy()
                self.after(0, done)

            threading.Thread(target=worker, daemon=True).start()

        btn_ok.configure(command=on_apply)



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

        self.logout_button = ctk.CTkButton(self.tab_view.tab("Настройки"), text="Выйти", command=self.handle_logout, width=200)
        self.logout_button.pack(side='bottom', pady=50)

    def create_registry_tab(self, tab):
        columns = {
            "created_by": "Создал", 
            "driver": "Водитель",
            "driver2": "2-й Водитель",
            "number": "ТС",
            "pod": "Подрядчик",
            "marsh": "Маршрут",
            "numberPL": "№ ПЛ",
            "gruz": "Груз",
            "dataPOPL": "Дата выдачи",
            "dataSDPL": "Дата сдачи",
            "numberTN": "№ ТТН",
            "loading_time": "Погрузка",
            "unloading_time": "Разгрузка",
            "tonn": "Тоннаж",
            "fuel_consumption": "ГСМ",
            "dispatch_info": "Отправка",
            "comment": "Комментарий",
        }
        
        # НОВОЕ: словарь ширин столбцов (можете настроить под свои нужды)
        column_widths = {
            "#": 50,
            "created_by": 800,
            "driver": 200,
            "driver2": 150,
            "number": 80,
            "pod": 150,
            "marsh": 50,
            "numberPL": 130,
            "gruz": 120,
            "dataPOPL": 150,
            "dataSDPL": 150,
            "numberTN": 120,
            "loading_time": 150,
            "unloading_time": 150,
            "tonn": 80,
            "fuel_consumption": 100,
            "dispatch_info": 120,
            "comment": 200,
        }
        
        self.registry_table = DataTable(
            tab,
            self.api_client,
            'registries',
            columns,
            column_widths=column_widths,  # НОВОЕ: передаем ширины
            sync_callback=self.sync_callback,
            upload_callback=self.upload_pending
        )
        self.registry_table.pack(fill="both", expand=True)

    def upload_pending(self):
        if not self.api_client.is_network_ready():
            messagebox.showerror("Ошибка", "Нет подключения к серверу")
            return
        pending_items = self.api_client.get_pending_queue('registries')
        conflict_items = self.api_client.get_conflict_items()
        if len(pending_items) == 0 and len(conflict_items or []) == 0:
            messagebox.showinfo("Информация", "Нет данных для отправки")
            return

        def worker():
            try:
                success, conflicts = self.api_client.upload_pending_registries()
                self.after(0, self.reload_registry_table)
                msg = f"Отправлено успешно: {success}\n"
                if conflicts > 0:
                    msg += f"Обнаружено конфликтов: {conflicts}\n(показаны желтым цветом)"
                self.after(0, lambda: messagebox.showinfo("Результат отправки", msg))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Ошибка", f"Ошибка отправки: {e}"))
        threading.Thread(target=worker, daemon=True).start()

    def create_pl_creation_tab(self, tab):
        self.pl_form = CreatePLForm(tab, self.api_client, on_save_callback=self.reload_registry_table)
        self.pl_form.pack(fill="both", expand=True)

    def reload_pl_creation_tab(self):
        if hasattr(self, 'pl_form') and self.pl_form.winfo_exists():
            self.pl_form.reload_settings()
        else:
            self.create_pl_creation_tab(self.tab_view.tab("Создать ПЛ"))

    def reload_registry_table(self):
        if hasattr(self, 'registry_table'):
            self.registry_table.reload_table_data()
            self.tab_view.set("Реестр")

    def create_drivers_tab(self, tab):
        # Столбцы: ФИО, подрядчик, № ТС, марка, модель, телефон, статус (русский текст)
        columns = {
            'full_name': 'ФИО',
            'contractor': 'Подрядчик',
            'cars': '№ ТС',
            'marka': 'Марка',
            'model': 'Модель',
            'phone_1': 'Телефон',
            'status': 'Статус'
        }
        DataTable(tab, self.api_client, 'drivers', columns, can_edit=False).pack(fill="both", expand=True)

    def create_contractors_tab(self, tab):
        # Столбцы: название, руководитель, телефон, статус (русский текст)
        columns = {
            'org_name': 'Название',
            'full_name': 'Руководитель',
            'phone_1': 'Телефон',
            'status': 'Статус'
        }
        DataTable(tab, self.api_client, 'podryads', columns, can_edit=False).pack(fill="both", expand=True)

    def create_settings_tab(self, tab):
        self.settings_frame = SettingsForm(tab, self.api_client, on_save_callback=self.reload_pl_creation_tab)
        self.settings_frame.pack(fill="both", expand=True, padx=20, pady=20)

        #Информация о пользователе над кнопкой "Выйти"
        user_info_frame = ctk.CTkFrame(tab, fg_color="transparent")
        user_info_frame.pack(side='bottom', fill='x', padx=20, pady=(10, 0))
        
        username = self.api_client.current_user or "Не авторизован"
        user_id = self.api_client.current_user_id or "N/A"
        
        user_text = f"👤 Пользователь: {username} (ID: {user_id})"
        
        user_label = ctk.CTkLabel(
            user_info_frame, 
            text=user_text,
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="center"
        )
        user_label.pack(pady=(0, 10))
        
        # Кнопка "Выйти" теперь под информацией о пользователе
        self.logout_button = ctk.CTkButton(
            user_info_frame, 
            text="Выйти", 
            command=self.handle_logout, 
            width=200,
            fg_color="#c62828"
        )
        self.logout_button.pack(pady=(0, 20))

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
