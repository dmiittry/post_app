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
            text="Настройки клиента",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        self.title_label.pack(pady=(0, 20), anchor="w")

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

    # ---------- Persistence ----------
    def save_settings(self):
        """Сохраняет настройки в кэш"""
        settings = {}
        
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

        # excel_output_dir
        excel_dir = settings.get('excel_output_dir')
        if excel_dir:
            self.excel_dir_var.set(excel_dir)
        else:
            # дефолт — папка программы/Путевые листы
            self.excel_dir_var.set(str(Path.cwd() / "Путевые листы"))
