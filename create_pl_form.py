# create_pl_form.py

import customtkinter as ctk
from tkinter import messagebox
from tkcalendar import DateEntry
from datetime import datetime
import uuid
import threading

class CreatePLForm(ctk.CTkFrame):
    def __init__(self, master, api_client, on_save_callback, **kwargs):
        super().__init__(master, fg_color="transparent")
        
        self.api_client = api_client
        self.on_save_callback = on_save_callback
        self.form_widgets = {}
        self.default_settings = {}
        self.related_data = {}
        
        # Создаем внутренний прокручиваемый фрейм для полей
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_frame.pack(fill="both", expand=True)
        self.scroll_frame.grid_columnconfigure(1, weight=1)
        
        # Создаем нижний фрейм для кнопки
        self.bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.bottom_frame.pack(fill="x", pady=(10, 0))
        
        self.submit_button = ctk.CTkButton(
            self.bottom_frame, 
            text="Создать путевой лист", 
            command=self.submit_form
        )
        self.submit_button.pack(pady=(5, 10), padx=20)
        
        self._load_data()
        self._create_widgets()
        self._apply_defaults()

    def _load_data(self):
        """Загрузка справочников и настроек по умолчанию"""
        self.default_settings = self.api_client.cache.load_data('default_pl_settings') or {}
        
        endpoints = [
            'seasons', 'organizations', 'customers', 'gruzes', 'cargo-batches',
            'drivers', 'cars', 'podryads', 'loading-points', 'unloading-points',
            'car-markas', 'car-models'
        ]
        
        for endpoint in endpoints:
            self.related_data[endpoint] = self.api_client.get_local_data(endpoint) or []
        
        self.drivers_by_id = {d['id']: d for d in self.related_data['drivers']}
        self.cars_by_id = {c['id']: c for c in self.related_data['cars']}
        self.markas_by_id = {m['id']: m for m in self.related_data['car-markas']}
        self.models_by_id = {m['id']: m for m in self.related_data['car-models']}
        self.podryads_by_id = {p['id']: p for p in self.related_data['podryads']}
        self.gruzes_by_id = {g['id']: g for g in self.related_data['gruzes']}

    def _create_widgets(self):
        row_counter = 0
        parent = self.scroll_frame
        
        def add_field(row, label_text, api_key, widget_type, values=None, **kwargs):
            label = ctk.CTkLabel(parent, text=label_text, anchor="w")
            label.grid(row=row, column=0, sticky="w", padx=(20, 10), pady=5)
            
            widget_container = ctk.CTkFrame(parent, fg_color="transparent")
            widget_container.grid(row=row, column=1, sticky="ew", padx=(0, 20), pady=5)
            
            widget = None
            
            if widget_type == "entry":
                widget = ctk.CTkEntry(widget_container, **kwargs)
                widget.pack(fill="x")
            elif widget_type == "combobox":
                widget = ctk.CTkComboBox(widget_container, values=values, state="readonly", **kwargs)
                widget.pack(fill="x")
            elif widget_type == "label":
                widget = ctk.CTkLabel(widget_container, text=kwargs.pop('text', ''), anchor="w", **kwargs)
                widget.pack(fill="x")
            elif widget_type == "datetime":
                date_entry = DateEntry(widget_container, date_pattern='dd.mm.yyyy', width=12)
                hour_combo = ctk.CTkComboBox(widget_container, width=70, values=[f"{h:02d}" for h in range(24)])
                minute_combo = ctk.CTkComboBox(widget_container, width=70, values=[f"{m:02d}" for m in range(0, 60, 5)])
                
                date_entry.pack(side="left")
                hour_combo.pack(side="left", padx=5)
                minute_combo.pack(side="left")
                
                widget = (date_entry, hour_combo, minute_combo)
            
            self.form_widgets[api_key] = widget
            return widget
        
        # --- Секция настроек ---
        ctk.CTkLabel(parent, text="Параметры по умолчанию (из Настроек)", 
                     font=ctk.CTkFont(weight='bold')).grid(row=row_counter, column=0, columnspan=2, sticky="w", padx=20, pady=(10, 5))
        row_counter += 1
        
        add_field(row_counter, "Сезон:", "season", "label"); row_counter += 1
        add_field(row_counter, "Организация:", "organization", "label"); row_counter += 1
        add_field(row_counter, "Заказчик:", "customer", "label"); row_counter += 1
        add_field(row_counter, "Вид груза:", "gruz", "label", font=ctk.CTkFont(weight='bold')); row_counter += 1  # ДОБАВЛЕНО: жирный шрифт
        add_field(row_counter, "Место погрузки:", "loading_point", "label"); row_counter += 1
        add_field(row_counter, "Место разгрузки:", "unloading_point", "label"); row_counter += 1
        add_field(row_counter, "Расстояние, км:", "distance", "label"); row_counter += 1
        add_field(row_counter, "Маршрут:", "marsh", "label", font=ctk.CTkFont(weight='bold')); row_counter += 1
        add_field(row_counter, "Номер ПЛ:", "numberPL", "label", font=ctk.CTkFont(weight='bold', size=14), text_color="green"); row_counter += 1  # НОВОЕ: поле для номера ПЛ
        
        # --- Секция данных ПЛ ---
        ctk.CTkLabel(parent, text="Данные Путевого Листа", 
                     font=ctk.CTkFont(weight='bold')).grid(row=row_counter, column=0, columnspan=2, sticky="w", padx=20, pady=(20, 5))
        row_counter += 1
        
        driver1_widget = add_field(row_counter, "Водитель 1", "driver", "entry", 
                                   placeholder_text="Введите ФИО и нажмите Enter")
        row_counter += 1
        driver1_widget.bind("<Return>", lambda e: self._search_driver("driver"))
        
        add_field(row_counter, "  СНИЛС:", "snils", "label"); row_counter += 1
        add_field(row_counter, "  ВУ:", "driver_license", "label"); row_counter += 1
        
        driver2_widget = add_field(row_counter, "Водитель 2", "driver2", "entry", 
                                   placeholder_text="Введите ФИО и нажмите Enter")
        row_counter += 1
        driver2_widget.bind("<Return>", lambda e: self._search_driver("driver2"))
        
        add_field(row_counter, "  СНИЛС 2:", "snils2", "label"); row_counter += 1
        add_field(row_counter, "  ВУ 2:", "driver_license2", "label"); row_counter += 1
        
        add_field(row_counter, "ТС:", "number", "label"); row_counter += 1
        add_field(row_counter, "  Марка:", "marka", "label"); row_counter += 1
        add_field(row_counter, "  Модель:", "model", "label"); row_counter += 1
        add_field(row_counter, "Подрядчик:", "contractor", "label", font=ctk.CTkFont(weight='bold')); row_counter += 1  # ДОБАВЛЕНО: жирный шрифт
        
        batch_values = [b.get('batch_number', '') for b in self.related_data.get('cargo-batches', [])]
        add_field(row_counter, "Партия груза:", "cargo_batch", "combobox", values=batch_values)
        row_counter += 1
        
        date_widget, hour_widget, minute_widget = add_field(row_counter, "Дата выдачи ПЛ:", "dataPOPL", "datetime")
        row_counter += 1
        
        now = datetime.now()
        date_widget.set_date(now)
        hour_widget.set(f"{now.hour:02d}")
        minute_widget.set(f"{int(now.minute / 5) * 5:02d}")
        
        self.selected_ids = {}

    def _apply_defaults(self):
        defaults = self.default_settings
        
        print("=== ПРИМЕНЕНИЕ НАСТРОЕК ПО УМОЛЧАНИЮ ===")
        print(f"Настройки: {defaults}")
        
        def get_name_by_id(data_list, item_id, key='name'):
            item = next((i for i in data_list if str(i.get('id')) == str(item_id)), None)
            return item.get(key) if item else ""
        
        self.form_widgets['season'].configure(text=get_name_by_id(self.related_data['seasons'], defaults.get('season')))
        self.form_widgets['organization'].configure(text=get_name_by_id(self.related_data['organizations'], defaults.get('organization')))
        self.form_widgets['customer'].configure(text=get_name_by_id(self.related_data['customers'], defaults.get('customer')))
        
        # ИСПРАВЛЕНО: отображаем вид груза с логированием
        gruz_id = defaults.get('gruz')
        print(f"Вид груза ID: {gruz_id}")
        
        if gruz_id:
            gruz_item = next((g for g in self.related_data['gruzes'] if g.get('id') == gruz_id), None)
            if gruz_item:
                gruz_name = gruz_item.get('name', '')
                print(f"Вид груза найден: {gruz_name}")
                self.form_widgets['gruz'].configure(text=gruz_name)
            else:
                print(f"Вид груза не найден в справочнике")
                self.form_widgets['gruz'].configure(text="")
        else:
            print("Вид груза не установлен в настройках")
            self.form_widgets['gruz'].configure(text="")
        
        self.form_widgets['loading_point'].configure(text=get_name_by_id(self.related_data['loading-points'], defaults.get('loading_point')))
        self.form_widgets['unloading_point'].configure(text=get_name_by_id(self.related_data['unloading-points'], defaults.get('unloading_point')))
        self.form_widgets['distance'].configure(text=defaults.get('distance', ''))
        
        # ВАЖНО: генерируем маршрут и номер ПЛ
        self._generate_marsh()
        print("===========================================")


    def _generate_marsh(self):
        """Генерирует код маршрута"""
        def get_short_name(data_list, item_id):
            item = next((i for i in data_list if str(i.get('id')) == str(item_id)), None)
            if not item:
                return ""
            return item.get('short_name') or (item.get('name')[0] if item.get('name') else "")
        
        lp_id = self.default_settings.get('loading_point')
        up_id = self.default_settings.get('unloading_point')
        gruz_id = self.default_settings.get('gruz')
        
        lp_char = get_short_name(self.related_data['loading-points'], lp_id)
        up_char = get_short_name(self.related_data['unloading-points'], up_id)
        gruz_char = get_short_name(self.related_data['gruzes'], gruz_id)
        
        if lp_char and up_char and gruz_char:
            marsh_code = f"{lp_char}{up_char}-{gruz_char}"
            self.form_widgets['marsh'].configure(text=marsh_code)
            
            # НОВОЕ: генерируем номер ПЛ
            self._generate_numberPL(marsh_code)
        else:
            self.form_widgets['marsh'].configure(text="")
            self.form_widgets['numberPL'].configure(text="")

    def _generate_numberPL(self, marsh_code):
        """Генерирует номер путевого листа"""
        if not marsh_code:
            return
        
        season_id = self.default_settings.get('season')
        if not season_id:
            return
        
        # Считаем количество записей с таким маршрутом в этом сезоне
        registries = self.api_client.get_local_data('registries') or []
        
        count = 0
        for reg in registries:
            if isinstance(reg, dict):
                if reg.get('marsh') == marsh_code and reg.get('season') == season_id:
                    count += 1
        
        # Также учитываем pending записи
        pending = self.api_client.get_local_data('pending_registries') or []
        for reg in pending:
            if isinstance(reg, dict):
                if reg.get('marsh') == marsh_code and reg.get('season') == season_id:
                    count += 1
        
        new_number = f"{marsh_code}-{count + 1}"
        self.form_widgets['numberPL'].configure(text=new_number)

    def _search_driver(self, key):
        query = self.form_widgets[key].get().lower()
        if not query:
            return
        
        results = [d for d in self.related_data['drivers'] if query in d['full_name'].lower()]
        
        if not results:
            messagebox.showinfo("Поиск", f"Водитель с '{query}' не найден.")
            return
        
        if len(results) == 1:
            self._select_driver(results[0], key)
        else:
            top = ctk.CTkToplevel(self)
            top.title("Выберите водителя")
            top.geometry("400x300")
            top.transient(self)
            top.grab_set()
            
            def on_select(driver):
                self._select_driver(driver, key)
                top.destroy()
            
            for driver in results:
                ctk.CTkButton(top, text=driver['full_name'], 
                             command=lambda d=driver: on_select(d)).pack(pady=5, padx=10, fill='x')

    def _load_data(self):
        """Загрузка справочников и настроек по умолчанию"""
        self.default_settings = self.api_client.cache.load_data('default_pl_settings') or {}
        
        endpoints = [
            'seasons', 'organizations', 'customers', 'gruzes', 'cargo-batches',
            'drivers', 'cars', 'podryads', 'loading-points', 'unloading-points',
            'car-markas', 'car-models'
        ]
        
        for endpoint in endpoints:
            self.related_data[endpoint] = self.api_client.get_local_data(endpoint) or []
        
        self.drivers_by_id = {d['id']: d for d in self.related_data['drivers']}
        self.cars_by_id = {c['id']: c for c in self.related_data['cars']}
        self.markas_by_id = {m['id']: m for m in self.related_data['car-markas']}
        self.models_by_id = {m['id']: m for m in self.related_data['car-models']}
        self.podryads_by_id = {p['id']: p for p in self.related_data['podryads']}
        self.gruzes_by_id = {g['id']: g for g in self.related_data['gruzes']}
        
        # НОВОЕ: Создаем индекс водитель -> подрядчик
        self.driver_to_podryad = self._build_driver_contractor_index()

    def _build_driver_contractor_index(self):
        """
        Строит индекс: {driver_id: contractor_id}
        Ищет водителей в списке drivers каждого подрядчика
        """
        index = {}
        
        for podryad in self.related_data['podryads']:
            podryad_id = podryad.get('id')
            driver_ids = podryad.get('drivers', [])
            
            # driver_ids может быть списком ID
            if isinstance(driver_ids, list):
                for driver_id in driver_ids:
                    if driver_id:
                        index[driver_id] = podryad_id
                        print(f"-> Связь: Водитель {driver_id} -> Подрядчик {podryad_id} ({podryad.get('org_name')})")
        
        print(f"-> Всего связей водитель-подрядчик: {len(index)}")
        return index

    def _select_driver(self, driver_data, key):
        self.form_widgets[key].delete(0, 'end')
        self.form_widgets[key].insert(0, driver_data['full_name'])
        self.selected_ids[key] = driver_data['id']
        
        snils = driver_data.get('snils') or 'механик'
        vu = driver_data.get('driver_license') or 'механик'
        
        if key == 'driver':
            self.form_widgets['snils'].configure(text=snils)
            self.form_widgets['driver_license'].configure(text=vu)
            
            car_id = (driver_data.get('cars') or [None])[0]
            driver_id = driver_data.get('id')
            
            # Очищаем предыдущие данные
            for k in ['number', 'marka', 'model', 'pod']:
                self.selected_ids.pop(k, None)
            for w_key in ['number', 'marka', 'model', 'contractor']:
                self.form_widgets[w_key].configure(text="")
            
            # Заполняем данные ТС
            if car_id and car_id in self.cars_by_id:
                car = self.cars_by_id[car_id]
                self.selected_ids['number'] = car['id']
                self.form_widgets['number'].configure(text=car.get('number', ''))
                
                marka = self.markas_by_id.get(car.get('marka'), {}).get('name', '')
                model = self.models_by_id.get(car.get('model'), {}).get('name', '')
                
                self.form_widgets['marka'].configure(text=marka)
                self.form_widgets['model'].configure(text=model)
            
            # НОВОЕ: Ищем подрядчика через индекс
            print(f"-> Поиск подрядчика для водителя ID: {driver_id}")
            
            if driver_id in self.driver_to_podryad:
                podryad_id = self.driver_to_podryad[driver_id]
                print(f"-> Найден подрядчик ID: {podryad_id}")
                
                if podryad_id in self.podryads_by_id:
                    podryad = self.podryads_by_id[podryad_id]
                    self.selected_ids['pod'] = podryad['id']
                    self.form_widgets['contractor'].configure(text=podryad.get('org_name', ''))
                    print(f"-> Подрядчик установлен: {podryad.get('org_name')} (ID: {podryad['id']})")
                else:
                    print(f"-> ОШИБКА: Подрядчик ID {podryad_id} не найден в справочнике podryads")
            else:
                print(f"-> ВНИМАНИЕ: Водитель ID {driver_id} не привязан ни к одному подрядчику")
                print(f"-> Доступные связи: {list(self.driver_to_podryad.keys())[:10]}...")
        
        elif key == 'driver2':
            self.form_widgets['snils2'].configure(text=snils)
            self.form_widgets['driver_license2'].configure(text=vu)


    def reload_settings(self):
        """Перезагружает настройки и обновляет отображение"""
        self.default_settings = self.api_client.cache.load_data('default_pl_settings') or {}
        self._apply_defaults()

    def submit_form(self):
        payload = {}
        
        # Добавляем настройки по умолчанию
        for key in ['season', 'organization', 'customer', 'gruz', 'loading_point', 'unloading_point']:
            if self.default_settings.get(key):
                payload[key] = self.default_settings.get(key)
        
        if self.default_settings.get('distance'):
            payload['distance'] = str(self.default_settings.get('distance'))
        
        # Добавляем выбранных водителей и ТС
        for key in ['driver', 'driver2', 'number', 'pod']:
            if self.selected_ids.get(key):
                payload[key] = self.selected_ids.get(key)
        
        # НОВОЕ: добавляем marsh и numberPL
        payload['marsh'] = self.form_widgets['marsh'].cget("text")
        payload['numberPL'] = self.form_widgets['numberPL'].cget("text")
        
        # Партия груза
        batch_name = self.form_widgets['cargo_batch'].get()
        if batch_name:
            batch_item = next((b for b in self.related_data.get('cargo-batches', []) 
                              if b['batch_number'] == batch_name), None)
            if batch_item:
                payload['cargo_batch'] = batch_item['id']
        
        # Дата выдачи ПЛ
        try:
            date_widget, hour_widget, minute_widget = self.form_widgets['dataPOPL']
            date_val = date_widget.get_date()
            hour_val = int(hour_widget.get())
            minute_val = int(minute_widget.get())
            full_datetime = datetime(date_val.year, date_val.month, date_val.day, hour_val, minute_val)
            payload['dataPOPL'] = full_datetime.isoformat()
        except Exception as e:
            print(f"Error getting date: {e}")
            pass
        
        payload['temp_id'] = f"temp_{uuid.uuid4()}"
        
        if 'driver' not in payload:
            messagebox.showerror("Ошибка", "Необходимо выбрать основного водителя!")
            return
        
        # Проверяем обязательные поля
        if not payload.get('marsh'):
            messagebox.showerror("Ошибка", "Маршрут не сгенерирован. Проверьте настройки.")
            return
        
        if not payload.get('numberPL'):
            messagebox.showerror("Ошибка", "Номер ПЛ не сгенерирован. Проверьте настройки.")
            return
        
        # Сохраняем локально в очередь
        self.api_client.add_to_pending_queue('registries', payload)
        
        # Обновляем таблицу
        if self.on_save_callback:
            self.on_save_callback()
        
        messagebox.showinfo("Успех", f"Путевой лист {payload['numberPL']} сохранен локально.\nБудет отправлен при синхронизации.")
        
        # Пытаемся отправить в фоне
        threading.Thread(target=self.api_client.try_send_single_item, 
                        args=('registries', payload['temp_id']), daemon=True).start()
        
        # Обновляем номер ПЛ для следующей записи
        self._generate_numberPL(payload['marsh'])
