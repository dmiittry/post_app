# settings_form.py

import customtkinter as ctk
from tkinter import messagebox
import tkinter.filedialog as fd
from pathlib import Path


class SettingsForm(ctk.CTkFrame):
    """
    Форма для управления настройками по умолчанию для Путевого Листа.
    """
    def __init__(self, master, api_client, on_save_callback=None):
        super().__init__(master, fg_color="transparent")

        self.api_client = api_client
        self.on_save_callback = on_save_callback
        self.cache_key = 'default_pl_settings'
        self.fields = {}

        self.title_label = ctk.CTkLabel(
            self,
            text="Настройки по умолчанию для Путевого Листа",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        self.title_label.pack(pady=(0, 20), anchor="w")

        # Справочники
        self.related_data = {
            "seasons": self.api_client.get_local_data('seasons') or [],
            "organizations": self.api_client.get_local_data('organizations') or [],
            "customers": self.api_client.get_local_data('customers') or [],
            "gruzes": self.api_client.get_local_data('gruzes') or [],
            "loading-points": self.api_client.get_local_data('loading-points') or [],
            "unloading-points": self.api_client.get_local_data('unloading-points') or [],
        }

        # Поля-списки
        self.create_combobox("Сезон", "season", [s.get('name', '') for s in self.related_data['seasons']])
        self.create_combobox("Организация", "organization", [o.get('name', '') for o in self.related_data['organizations']])
        self.create_combobox("Заказчик", "customer", [c.get('name', '') for c in self.related_data['customers']])
        self.create_combobox("Вид груза", "gruz", [g.get('name', '') for g in self.related_data['gruzes']])
        self.create_combobox("Место погрузки", "loading_point", [lp.get('name', '') for lp in self.related_data['loading-points']])
        self.create_combobox("Место разгрузки", "unloading_point", [up.get('name', '') for up in self.related_data['unloading-points']])

        # Поля-тексты
        self.create_entry("Расстояние, км", "distance")
        self.create_entry("Диспетчер:", "dispatcher")

        # Папка для путевых листов
        self.excel_dir_var = ctk.StringVar()
        saved_defaults = self.api_client.cache.load_data(self.cache_key) or {}
        self.excel_dir_var.set(saved_defaults.get('excel_output_dir', str((Path.cwd() / "Путевые листы"))))

        def choose_excel_dir():
            path = fd.askdirectory(title="Выберите папку для путевых листов")
            if path:
                self.excel_dir_var.set(path)

        excel_frame = ctk.CTkFrame(self, fg_color="transparent")
        excel_frame.pack(fill="x", padx=10, pady=(10, 0))
        ctk.CTkLabel(excel_frame, text="Папка путевых листов:", anchor="w").pack(side="left", padx=(0, 6))
        ctk.CTkEntry(excel_frame, textvariable=self.excel_dir_var, width=380).pack(side="left", padx=(0, 6))
        ctk.CTkButton(excel_frame, text="Выбрать…", command=choose_excel_dir, width=90).pack(side="left")

        # Кнопка сохранения
        self.btn_save = ctk.CTkButton(self, text="Сохранить настройки", command=self.save_settings, width=220)
        self.btn_save.pack(pady=20)

        # Загрузка сохраненных значений
        self.load_settings()

    # ---------- UI helpers ----------
    def create_combobox(self, label_text, field_key, values):
        """Создает Combobox с меткой"""
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="x", pady=5, padx=10)

        label = ctk.CTkLabel(frame, text=label_text, width=150, anchor="w")
        label.pack(side="left", padx=(0, 10))

        combo = ctk.CTkComboBox(frame, values=values, width=300, state="readonly")
        combo.pack(side="left", fill="x", expand=True)

        self.fields[field_key] = combo

    def create_entry(self, label_text, field_key):
        """Создает Entry с меткой"""
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="x", pady=5, padx=10)

        label = ctk.CTkLabel(frame, text=label_text, width=150, anchor="w")
        label.pack(side="left", padx=(0, 10))

        entry = ctk.CTkEntry(frame, width=300)
        entry.pack(side="left", fill="x", expand=True)

        self.fields[field_key] = entry

    # ---------- Persistence ----------
    def save_settings(self):
        """Сохраняет настройки в кэш"""
        settings = {}

        # Сохраняем ID вместо названий
        for key in ['season', 'organization', 'customer', 'gruz', 'loading_point', 'unloading_point']:
            if key in self.fields:
                selected_name = self.fields[key].get()

                # Определяем источник данных
                if key == 'loading_point':
                    data_key = 'loading-points'
                elif key == 'unloading_point':
                    data_key = 'unloading-points'
                elif key == 'gruz':
                    data_key = 'gruzes'
                else:
                    data_key = f"{key}s"

                # Ищем ID по имени
                item = next((i for i in self.related_data.get(data_key, []) if i.get('name') == selected_name), None)
                if item:
                    settings[key] = item['id']

        # Distance и dispatcher — как есть
        if 'distance' in self.fields:
            settings['distance'] = self.fields['distance'].get()
        if 'dispatcher' in self.fields:
            settings['dispatcher'] = self.fields['dispatcher'].get()

        # Папка Excel
        excel_dir = (self.excel_dir_var.get() or "").strip()
        if excel_dir:
            settings['excel_output_dir'] = excel_dir

        # Сохранить в кэш
        self.api_client.cache.save_data(self.cache_key, settings)

        messagebox.showinfo("Успех", "Настройки успешно сохранены!")

        # Обновить формы/вкладки по колбэку
        if self.on_save_callback:
            self.on_save_callback()

    def load_settings(self):
        """Загружает сохраненные настройки из кэша"""
        settings = self.api_client.cache.load_data(self.cache_key) or {}

        # Из ID -> имя в комбобоксах
        for key in ['season', 'organization', 'customer', 'gruz', 'loading_point', 'unloading_point']:
            if key in self.fields and key in settings:
                item_id = settings[key]

                # Определяем источник данных
                if key == 'loading_point':
                    data_key = 'loading-points'
                elif key == 'unloading_point':
                    data_key = 'unloading-points'
                elif key == 'gruz':
                    data_key = 'gruzes'
                else:
                    data_key = f"{key}s"

                # Найти по id и выставить name
                item = next((i for i in self.related_data.get(data_key, []) if i.get('id') == item_id), None)
                if item:
                    self.fields[key].set(item.get('name', ''))

        # distance
        if 'distance' in self.fields and 'distance' in settings:
            self.fields['distance'].delete(0, 'end')
            self.fields['distance'].insert(0, settings['distance'])

        # dispatcher
        if 'dispatcher' in self.fields and 'dispatcher' in settings:
            self.fields['dispatcher'].delete(0, 'end')
            self.fields['dispatcher'].insert(0, settings['dispatcher'])

        # excel_output_dir
        excel_dir = settings.get('excel_output_dir')
        if excel_dir:
            self.excel_dir_var.set(excel_dir)
        else:
            # дефолт — папка программы/Путевые листы
            self.excel_dir_var.set(str(Path.cwd() / "Путевые листы"))
