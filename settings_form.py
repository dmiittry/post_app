# settings_form.py

import customtkinter as ctk
from tkinter import messagebox

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
        
        # Словарь для хранения загруженных справочников
        self.related_data = {
            "seasons": self.api_client.get_local_data('seasons') or [],
            "organizations": self.api_client.get_local_data('organizations') or [],
            "customers": self.api_client.get_local_data('customers') or [],
            "gruzes": self.api_client.get_local_data('gruzes') or [],
            "loading-points": self.api_client.get_local_data('loading-points') or [],
            "unloading-points": self.api_client.get_local_data('unloading-points') or [],
        }
        
        # Создаем поля формы
        self.create_combobox("Сезон", "season", [s.get('name', '') for s in self.related_data['seasons']])
        self.create_combobox("Организация", "organization", [o.get('name', '') for o in self.related_data['organizations']])
        self.create_combobox("Заказчик", "customer", [c.get('name', '') for c in self.related_data['customers']])
        self.create_combobox("Вид груза", "gruz", [g.get('name', '') for g in self.related_data['gruzes']])
        self.create_combobox("Место погрузки", "loading_point", [lp.get('name', '') for lp in self.related_data['loading-points']])
        self.create_combobox("Место разгрузки", "unloading_point", [up.get('name', '') for up in self.related_data['unloading-points']])
        self.create_entry("Расстояние, км", "distance")
        
        # Кнопка сохранения
        self.btn_save = ctk.CTkButton(self, text="Сохранить настройки", command=self.save_settings, width=200)
        self.btn_save.pack(pady=20)
        
        # Загружаем сохраненные настройки
        self.load_settings()

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

    def save_settings(self):
        """Сохраняет настройки в кэш"""
        settings = {}
        
        # Сохраняем ID вместо названий
        for key in ['season', 'organization', 'customer', 'gruz', 'loading_point', 'unloading_point']:
            if key in self.fields:
                selected_name = self.fields[key].get()
                
                # Определяем источник данных
                data_key = key
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
        
        # Сохраняем distance как есть
        if 'distance' in self.fields:
            settings['distance'] = self.fields['distance'].get()
        
        # Сохраняем в кэш
        self.api_client.cache.save_data(self.cache_key, settings)
        
        messagebox.showinfo("Успех", "Настройки успешно сохранены!")
        
        # НОВОЕ: вызываем колбэк для обновления формы создания ПЛ
        if self.on_save_callback:
            self.on_save_callback()

    def load_settings(self):
        """Загружает сохраненные настройки из кэша"""
        settings = self.api_client.cache.load_data(self.cache_key) or {}
        
        # Загружаем значения из ID
        for key in ['season', 'organization', 'customer', 'gruz', 'loading_point', 'unloading_point']:
            if key in self.fields and key in settings:
                item_id = settings[key]
                
                # Определяем источник данных
                data_key = key
                if key == 'loading_point':
                    data_key = 'loading-points'
                elif key == 'unloading_point':
                    data_key = 'unloading-points'
                elif key == 'gruz':
                    data_key = 'gruzes'
                else:
                    data_key = f"{key}s"
                
                # Ищем имя по ID
                item = next((i for i in self.related_data.get(data_key, []) if i.get('id') == item_id), None)
                if item:
                    self.fields[key].set(item.get('name', ''))
        
        # Загружаем distance
        if 'distance' in self.fields and 'distance' in settings:
            self.fields['distance'].delete(0, 'end')
            self.fields['distance'].insert(0, settings['distance'])
