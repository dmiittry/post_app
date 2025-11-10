# login.py

import customtkinter as ctk
# ДОБАВИТЬ ВВЕРХУ
from urllib.parse import urlencode

import requests

class LoginFrame(ctk.CTkFrame):
    def __init__(self, master, login_callback):
        super().__init__(master, fg_color="transparent")
        self.login_callback = login_callback

        self.label = ctk.CTkLabel(self, text="Авторизация", font=ctk.CTkFont(size=24, weight="bold"))
        self.label.pack(pady=(100, 20))

        self.entry_username = ctk.CTkEntry(self, placeholder_text="Логин", width=300)
        self.entry_username.pack(pady=10)
        
        self.entry_password = ctk.CTkEntry(self, placeholder_text="Пароль", show="*", width=300)
        self.entry_password.pack(pady=10)
        
        self.remember_me_var = ctk.StringVar(value="off")
        self.remember_me_checkbox = ctk.CTkCheckBox(self, text="Запомнить меня", variable=self.remember_me_var, onvalue="on", offvalue="off")
        self.remember_me_checkbox.pack(pady=10)

        self.btn_login = ctk.CTkButton(self, text="Войти", command=self.on_login_press, width=300)
        self.btn_login.pack(pady=20)
        
        self.status_label = ctk.CTkLabel(self, text="", text_color="red")
        self.status_label.pack()
        self.current_user_id = None
        try:
            # Вариант 1: есть эндпоинт me
            me_resp = self.session.get(f"{self.base_url}users/me/", timeout=10)
            if me_resp.status_code == 200:
                me = me_resp.json()
                # ожидаем поле id
                if isinstance(me, dict) and me.get("id") is not None:
                    self.current_user_id = me.get("id")
            else:
                # Вариант 2: по имени через фильтр
                qs = urlencode({"username": username})
                list_resp = self.session.get(f"{self.base_url}users/?{qs}", timeout=10)
                if list_resp.status_code == 200:
                    data = list_resp.json()
                    if isinstance(data, list) and data:
                        first = data[0]
                        if isinstance(first, dict) and first.get("id") is not None:
                            self.current_user_id = first.get("id")
        except requests.exceptions.RequestException:
            # не критично — просто не будет id, сервер сам может проставить
            pass

    def on_login_press(self):
        """Просто передает данные для обработки в главный класс."""
        username = self.entry_username.get()
        password = self.entry_password.get()
        remember = self.remember_me_var.get() == "on"
        self.status_label.configure(text="Попытка входа...")
        self.update_idletasks()
        
        self.login_callback(username, password, remember) # Вызываем колбэк

    def show_error(self, message):
        """Показывает сообщение об ошибке."""
        self.status_label.configure(text=message)

                # ИЗМЕНЕНО: попытка узнать ID текущего пользователя

