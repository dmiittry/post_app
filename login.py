# login.py

import customtkinter as ctk

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
