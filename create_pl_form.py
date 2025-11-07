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

        # Внутренние индексы
        self.drivers_by_id = {}
        self.cars_by_id = {}
        self.markas_by_id = {}
        self.models_by_id = {}
        self.podryads_by_id = {}
        self.gruzes_by_id = {}
        self.driver_to_podryad = {}

        # Выбранные id для payload
        self.selected_ids = {}

        # Основной двухколоночный макет
        self.grid_columnconfigure(0, weight=1, uniform="cols")
        self.grid_columnconfigure(1, weight=2, uniform="cols")
        self.grid_rowconfigure(0, weight=1)

        # Левая колонка: настройки по умолчанию (скроллируемая)
        self.left_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.left_frame.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)
        self.left_frame.grid_columnconfigure(0, weight=1)
        self.left_frame.grid_columnconfigure(1, weight=1)

        # Правая колонка: форма ПЛ (скроллируемая)
        self.right_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.right_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 10), pady=10)
        self.right_frame.grid_columnconfigure(0, weight=1)
        self.right_frame.grid_columnconfigure(1, weight=1)

        # Нижняя полоса с кнопкой отправки (фиксированная)
        self.bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.bottom_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 10))
        self.bottom_frame.grid_columnconfigure(0, weight=1)

        self.submit_button = ctk.CTkButton(
            self.bottom_frame,
            text="Создать путевой лист",
            command=self.submit_form,
            height=36
        )
        self.submit_button.grid(row=0, column=0, sticky="e")

        # Загрузка данных и построение UI
        self._load_data()
        self._build_left_settings_panel()
        self._build_right_pl_panel()
        self._apply_defaults()

    # ------------------------------
    # Загрузка справочников и индексов
    # ------------------------------
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

        self.drivers_by_id = {d['id']: d for d in self.related_data['drivers'] if isinstance(d, dict) and d.get('id') is not None}
        self.cars_by_id = {c['id']: c for c in self.related_data['cars'] if isinstance(c, dict) and c.get('id') is not None}
        self.markas_by_id = {m['id']: m for m in self.related_data['car-markas'] if isinstance(m, dict) and m.get('id') is not None}
        self.models_by_id = {m['id']: m for m in self.related_data['car-models'] if isinstance(m, dict) and m.get('id') is not None}
        self.podryads_by_id = {p['id']: p for p in self.related_data['podryads'] if isinstance(p, dict) and p.get('id') is not None}
        self.gruzes_by_id = {g['id']: g for g in self.related_data['gruzes'] if isinstance(g, dict) and g.get('id') is not None}

        # Индекс водитель -> подрядчик по массиву drivers в подряде
        self.driver_to_podryad = self._build_driver_contractor_index()

    def _build_driver_contractor_index(self):
        """
        Строит индекс: {driver_id: contractor_id}
        Ищет водителей в списке drivers каждого подрядчика (поддержка как списка ID, так и списка объектов).
        """
        index = {}
        for podryad in self.related_data['podryads']:
            if not isinstance(podryad, dict):
                continue
            podryad_id = podryad.get('id')
            drivers = podryad.get('drivers', [])
            if isinstance(drivers, list):
                for item in drivers:
                    if isinstance(item, dict):
                        driver_id = item.get('id')
                    elif isinstance(item, int):
                        driver_id = item
                    else:
                        driver_id = None
                    if driver_id:
                        index[driver_id] = podryad_id
        return index

    # ------------------------------
    # Построение UI: левая колонка (настройки)
    # ------------------------------
    def _build_left_settings_panel(self):
        row = 0
        ctk.CTkLabel(
            self.left_frame,
            text="Настройки по умолчанию",
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=row, column=0, columnspan=2, sticky="w", padx=10, pady=(5, 10))
        row += 1

        def add_setting(label_text, key, bold=False):
            nonlocal row
            font = ctk.CTkFont(weight="bold") if bold else None
            ctk.CTkLabel(self.left_frame, text=label_text, anchor="w").grid(row=row, column=0, sticky="w", padx=(10, 6), pady=4)
            lbl = ctk.CTkLabel(self.left_frame, text="", anchor="w", font=font)
            lbl.grid(row=row, column=1, sticky="ew", padx=(0, 10), pady=4)
            self.form_widgets[key] = lbl
            row += 1

        add_setting("Сезон:", "season")
        add_setting("Организация:", "organization")
        add_setting("Заказчик:", "customer")
        add_setting("Вид груза:", "gruz", bold=True)
        add_setting("Место погрузки:", "loading_point")
        add_setting("Место разгрузки:", "unloading_point")
        add_setting("Расстояние, км:", "distance")

        ctk.CTkLabel(self.left_frame, text="Подсказки", font=ctk.CTkFont(weight="bold")).grid(row=row, column=0, columnspan=2, sticky="w", padx=10, pady=(12, 6))
        row += 1
        ctk.CTkLabel(
            self.left_frame,
            text="Измените значения на вкладке «Настройки», затем вернитесь сюда — маршрут и № ПЛ пересчитаются автоматически.",
            wraplength=360,
            anchor="w",
            justify="left"
        ).grid(row=row, column=0, columnspan=2, sticky="w", padx=10, pady=(0, 10))
        row += 1

    # ------------------------------
    # Построение UI: правая колонка (ПЛ)
    # ------------------------------
    def _build_right_pl_panel(self):
        row = 0
        ctk.CTkLabel(
            self.right_frame,
            text="Путевой лист",
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=row, column=0, columnspan=2, sticky="w", padx=10, pady=(5, 10))
        row += 1

        def add_field(label_text, api_key, widget_type, values=None, **kwargs):
            nonlocal row
            ctk.CTkLabel(self.right_frame, text=label_text, anchor="w").grid(row=row, column=0, sticky="w", padx=(10, 6), pady=4)
            cont = ctk.CTkFrame(self.right_frame, fg_color="transparent")
            cont.grid(row=row, column=1, sticky="ew", padx=(0, 10), pady=4)
            widget = None

            if widget_type == "entry":
                widget = ctk.CTkEntry(cont, **kwargs)
                widget.pack(fill="x")
            elif widget_type == "combobox":
                widget = ctk.CTkComboBox(cont, values=values or [], state="readonly", **kwargs)
                widget.pack(fill="x")
            elif widget_type == "label":
                widget = ctk.CTkLabel(cont, text=kwargs.pop("text", ""), anchor="w", **kwargs)
                widget.pack(fill="x")
            elif widget_type == "datetime":
                date_entry = DateEntry(cont, date_pattern='dd.mm.yyyy', width=12)
                hour_combo = ctk.CTkComboBox(cont, width=70, values=[f"{h:02d}" for h in range(24)])
                minute_combo = ctk.CTkComboBox(cont, width=70, values=[f"{m:02d}" for m in range(0, 60, 5)])
                date_entry.pack(side="left")
                hour_combo.pack(side="left", padx=5)
                minute_combo.pack(side="left")
                widget = (date_entry, hour_combo, minute_combo)

            self.form_widgets[api_key] = widget
            row += 1
            return widget

        # Верхние вычисляемые поля ПЛ
        add_field("Маршрут:", "marsh", "label", font=ctk.CTkFont(weight="bold"))
        add_field("Номер ПЛ:", "numberPL", "label", font=ctk.CTkFont(weight="bold", size=14), text_color="green")

        # Данные водителей
        drv1 = add_field("Водитель 1", "driver", "entry", placeholder_text="Введите ФИО и нажмите Enter")
        drv1.bind("<Return>", lambda e: self._search_driver("driver"))
        add_field("  СНИЛС:", "snils", "label")
        add_field("  ВУ:", "driver_license", "label")

        drv2 = add_field("Водитель 2", "driver2", "entry", placeholder_text="Введите ФИО и нажмите Enter")
        drv2.bind("<Return>", lambda e: self._search_driver("driver2"))
        add_field("  СНИЛС 2:", "snils2", "label")
        add_field("  ВУ 2:", "driver_license2", "label")

        # ТС и подрядчик
        add_field("ТС:", "number", "label")
        add_field("  Марка:", "marka", "label")
        add_field("  Модель:", "model", "label")
        add_field("Подрядчик:", "contractor", "label", font=ctk.CTkFont(weight="bold"))

        # Партия груза
        batch_values = [b.get('batch_number', '') for b in self.related_data.get('cargo-batches', [])]
        add_field("Партия груза:", "cargo_batch", "combobox", values=batch_values)

        # Дата выдачи ПЛ
        date_widget, hour_widget, minute_widget = add_field("Дата выдачи ПЛ:", "dataPOPL", "datetime")

        # Значения по умолчанию для даты-времени
        now = datetime.now()
        date_widget.set_date(now)
        hour_widget.set(f"{now.hour:02d}")
        minute_widget.set(f"{int(now.minute / 5) * 5:02d}")

    # ------------------------------
    # Применение настроек и генерация marsh/numberPL
    # ------------------------------
    def _apply_defaults(self):
        defaults = self.default_settings

        def get_name_by_id(data_list, item_id, key='name'):
            item = next((i for i in data_list if str(i.get('id')) == str(item_id)), None)
            return item.get(key) if item else ""

        # Левая колонка (read-only отображение настроек)
        if 'season' in self.form_widgets:
            self.form_widgets['season'].configure(text=get_name_by_id(self.related_data['seasons'], defaults.get('season')))
        if 'organization' in self.form_widgets:
            self.form_widgets['organization'].configure(text=get_name_by_id(self.related_data['organizations'], defaults.get('organization')))
        if 'customer' in self.form_widgets:
            self.form_widgets['customer'].configure(text=get_name_by_id(self.related_data['customers'], defaults.get('customer')))

        gruz_id = defaults.get('gruz')
        if gruz_id and gruz_id in self.gruzes_by_id:
            self.form_widgets['gruz'].configure(text=self.gruzes_by_id[gruz_id].get('name', ''))
        else:
            self.form_widgets['gruz'].configure(text="")

        if 'loading_point' in self.form_widgets:
            self.form_widgets['loading_point'].configure(text=get_name_by_id(self.related_data['loading-points'], defaults.get('loading_point')))
        if 'unloading_point' in self.form_widgets:
            self.form_widgets['unloading_point'].configure(text=get_name_by_id(self.related_data['unloading-points'], defaults.get('unloading_point')))
        if 'distance' in self.form_widgets:
            self.form_widgets['distance'].configure(text=str(defaults.get('distance', '')))

        # Генерация маршрута и номера ПЛ в правой колонке
        self._generate_marsh()

    def _generate_marsh(self):
        """Генерирует код маршрута на основе настроек по умолчанию"""
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
            if 'marsh' in self.form_widgets:
                self.form_widgets['marsh'].configure(text=marsh_code)
            self._generate_numberPL(marsh_code)
        else:
            if 'marsh' in self.form_widgets:
                self.form_widgets['marsh'].configure(text="")
            if 'numberPL' in self.form_widgets:
                self.form_widgets['numberPL'].configure(text="")

    def _generate_numberPL(self, marsh_code):
        """Генерирует номер путевого листа в формате {marsh}-{seq} c учётом сезона и pending"""
        if not marsh_code:
            return
        season_id = self.default_settings.get('season')
        if not season_id:
            return

        registries = self.api_client.get_local_data('registries') or []
        pending = self.api_client.get_local_data('pending_registries') or []

        count = 0
        for reg in registries:
            if isinstance(reg, dict) and reg.get('marsh') == marsh_code and reg.get('season') == season_id:
                count += 1
        for reg in pending:
            if isinstance(reg, dict) and reg.get('marsh') == marsh_code and reg.get('season') == season_id:
                count += 1

        new_number = f"{marsh_code}-{count + 1}"
        if 'numberPL' in self.form_widgets:
            self.form_widgets['numberPL'].configure(text=new_number)

    # ------------------------------
    # Поиск и выбор водителей
    # ------------------------------
    def _search_driver(self, key):
        query = self.form_widgets[key].get().lower()
        if not query:
            return

        results = [d for d in self.related_data['drivers'] if isinstance(d, dict) and query in str(d.get('full_name', '')).lower()]

        if not results:
            messagebox.showinfo("Поиск", f"Водитель с '{query}' не найден.")
            return

        if len(results) == 1:
            self._select_driver(results[0], key)
        else:
            top = ctk.CTkToplevel(self)
            top.title("Выберите водителя")
            top.geometry("820x340")
            top.transient(self)
            top.grab_set()

            def on_select(driver):
                self._select_driver(driver, key)
                top.destroy()

            for driver in results:
                option_text = self._format_driver_option(driver)
                ctk.CTkButton(
                    top,
                    text=option_text,
                    command=lambda d=driver: on_select(d)
                ).pack(pady=5, padx=10, fill='x')

    def _format_driver_option(self, driver: dict) -> str:
        """Возвращает строку для кнопки выбора водителя: ФИО | ТС: НОМЕР | Подрядчик: Название"""
        # Номер ТС
        car_number = "—"
        car_ids = driver.get("cars") or []
        if isinstance(car_ids, list) and car_ids:
            first_car_id = car_ids[0]
            car = self.cars_by_id.get(first_car_id)
            if isinstance(car, dict):
                car_number = car.get("number") or "—"

        # Подрядчик (через индекс водитель -> подрядчик)
        contractor_name = "—"
        drv_id = driver.get("id")
        pod_id = self.driver_to_podryad.get(drv_id)
        if pod_id:
            pod = self.podryads_by_id.get(pod_id)
            if isinstance(pod, dict):
                contractor_name = pod.get("org_name") or "—"

        return f"{driver.get('full_name', 'Без имени')} | ТС: {car_number} | Подрядчик: {contractor_name}"


    def _select_driver(self, driver_data, key):
        self.form_widgets[key].delete(0, 'end')
        self.form_widgets[key].insert(0, driver_data['full_name'])
        self.selected_ids[key] = driver_data['id']

        snils = driver_data.get('snils') or 'механик'
        vu = driver_data.get('driver_license') or 'механик'

        if key == 'driver':
            # Основной водитель
            if 'snils' in self.form_widgets:
                self.form_widgets['snils'].configure(text=snils)
            if 'driver_license' in self.form_widgets:
                self.form_widgets['driver_license'].configure(text=vu)

            # Пробуем проставить ТС
            car_id = (driver_data.get('cars') or [None])[0]

            # Очистка
            for k in ['number', 'marka', 'model', 'pod']:
                self.selected_ids.pop(k, None)
            for w_key in ['number', 'marka', 'model', 'contractor']:
                if w_key in self.form_widgets:
                    self.form_widgets[w_key].configure(text="")

            if car_id and car_id in self.cars_by_id:
                car = self.cars_by_id[car_id]
                self.selected_ids['number'] = car['id']
                if 'number' in self.form_widgets:
                    self.form_widgets['number'].configure(text=car.get('number', ''))

                marka = self.markas_by_id.get(car.get('marka'), {}).get('name', '')
                model = self.models_by_id.get(car.get('model'), {}).get('name', '')
                if 'marka' in self.form_widgets:
                    self.form_widgets['marka'].configure(text=marka)
                if 'model' in self.form_widgets:
                    self.form_widgets['model'].configure(text=model)

            # Подрядчик по индексу водитель->подрядчик
            driver_id = driver_data.get('id')
            podryad_id = self.driver_to_podryad.get(driver_id)
            if podryad_id and podryad_id in self.podryads_by_id:
                podryad = self.podryads_by_id[podryad_id]
                self.selected_ids['pod'] = podryad['id']
                if 'contractor' in self.form_widgets:
                    self.form_widgets['contractor'].configure(text=podryad.get('org_name', ''))

        elif key == 'driver2':
            if 'snils2' in self.form_widgets:
                self.form_widgets['snils2'].configure(text=snils)
            if 'driver_license2' in self.form_widgets:
                self.form_widgets['driver_license2'].configure(text=vu)

    # ------------------------------
    # Отправка формы
    # ------------------------------
    def submit_form(self):
        payload = {}

        # Настройки по умолчанию
        for key in ['season', 'organization', 'customer', 'gruz', 'loading_point', 'unloading_point']:
            if self.default_settings.get(key):
                payload[key] = self.default_settings.get(key)

        if self.default_settings.get('distance'):
            payload['distance'] = str(self.default_settings.get('distance'))

        # Выбранные сущности
        for key in ['driver', 'driver2', 'number', 'pod']:
            if self.selected_ids.get(key):
                payload[key] = self.selected_ids.get(key)

        # Вычисляемые поля
        payload['marsh'] = self.form_widgets.get('marsh').cget("text") if self.form_widgets.get('marsh') else ""
        payload['numberPL'] = self.form_widgets.get('numberPL').cget("text") if self.form_widgets.get('numberPL') else ""

        # Партия груза
        cb = self.form_widgets.get('cargo_batch')
        if cb:
            batch_name = cb.get()
            if batch_name:
                batch_item = next((b for b in self.related_data.get('cargo-batches', []) if b.get('batch_number') == batch_name), None)
                if batch_item:
                    payload['cargo_batch'] = batch_item['id']

        # Дата выдачи
        try:
            date_widget, hour_widget, minute_widget = self.form_widgets['dataPOPL']
            date_val = date_widget.get_date()
            hour_val = int(hour_widget.get())
            minute_val = int(minute_widget.get())
            full_datetime = datetime(date_val.year, date_val.month, date_val.day, hour_val, minute_val)
            payload['dataPOPL'] = full_datetime.strftime("%Y-%m-%dT%H:%M:%S")
        except Exception as e:
            print(f"Error getting date: {e}")

        payload['temp_id'] = f"temp_{uuid.uuid4()}"

        # Валидация минимальная
        if 'driver' not in payload:
            messagebox.showerror("Ошибка", "Необходимо выбрать основного водителя!")
            return
        if not payload.get('marsh'):
            messagebox.showerror("Ошибка", "Маршрут не сгенерирован. Проверьте настройки.")
            return
        if not payload.get('numberPL'):
            messagebox.showerror("Ошибка", "Номер ПЛ не сгенерирован. Проверьте настройки.")
            return

        # Локально в очередь
        self.api_client.add_to_pending_queue('registries', payload)

        # Обновить таблицу
        if self.on_save_callback:
            self.on_save_callback()

        messagebox.showinfo("Успех", f"Путевой лист {payload['numberPL']} сохранен локально.\nБудет отправлен при синхронизации.")

        # Фоновая отправка
        threading.Thread(
            target=self.api_client.try_send_single_item,
            args=('registries', payload['temp_id']),
            daemon=True
        ).start()

        # Обновить номер для следующего ПЛ
        self._generate_numberPL(payload['marsh'])

    # ------------------------------
    # Публичное API для перезагрузки после изменения настроек
    # ------------------------------
    def reload_settings(self):
        """Перезагружает настройки, справочники и пересчитывает маршрут/номер ПЛ"""
        self._load_data()
        self._apply_defaults()
