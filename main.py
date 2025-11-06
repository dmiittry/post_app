# main.py

import customtkinter as ctk
import threading
from tkinter import messagebox
from login import LoginFrame
from tabs import MainApplicationFrame
from api_client import APIClient
from sync_window import SyncWindow
import requests

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

ENDPOINTS_TO_SYNC = [
    "podryads", "ie-profiles", "cars", "car-markas", "car-models",
    "drivers", "seasons", "gruzes", "loading-points",
    "unloading-points", "organizations", "customers", "cargo-batches",
]

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("А-Групп: Клиент управления")
        screen_width, screen_height = self.winfo_screenwidth(), self.winfo_screenheight()
        win_width, win_height = int(screen_width * 0.8), int(screen_height * 0.8)
        win_x, win_y = int((screen_width - win_width) / 2), int((screen_height - win_height) / 2)
        self.geometry(f"{win_width}x{win_height}+{win_x}+{win_y}")
        self.minsize(900, 700)
        
        self.api_client = APIClient()
        self.main_app_frame = None
        
        # НОВОЕ: Регистрируем колбэк для обновления UI
        self.api_client.set_data_updated_callback(self.on_data_updated)
        
        # Попытка автологина
        success, message = self.api_client.try_auto_login()
        
        if success:
            self.show_sync_and_load()
        else:
            self.show_login()

    def on_data_updated(self):
        """Вызывается когда данные обновлены (из фонового потока)"""
        # Используем after для обновления UI в главном потоке
        self.after(0, self.reload_registry_if_exists)

    def reload_registry_if_exists(self):
        """Перезагружает таблицу реестра, если она существует"""
        if self.main_app_frame and hasattr(self.main_app_frame, 'registry_table'):
            self.main_app_frame.registry_table.reload_table_data()

    def show_login(self):
        for widget in self.winfo_children():
            widget.destroy()
        login_frame = LoginFrame(self, login_callback=self.on_login)
        login_frame.pack(fill="both", expand=True)

    def on_login(self, username, password, remember_me):
        success, message = self.api_client.login(username, password, remember_me)
        
        if success:
            self.show_sync_and_load()
        else:
            messagebox.showerror("Ошибка авторизации", message)

    def show_sync_and_load(self):
        for widget in self.winfo_children():
            widget.destroy()
        
        sync_window = SyncWindow(self, total_steps=len(ENDPOINTS_TO_SYNC) + 1)
        
        def sync_data():
            sync_window.update_progress("Синхронизация справочников...")
            
            for endpoint in ENDPOINTS_TO_SYNC:
                self.api_client.sync_endpoint(endpoint, progress_callback=sync_window.update_progress)
            
            # Синхронизируем реестр
            self.api_client.sync_endpoint("registries", progress_callback=sync_window.update_progress)
            
            sync_window.update_progress("Синхронизация завершена.")
            sync_window.finish()
            
            self.after(500, self.show_main_app)
        
        threading.Thread(target=sync_data, daemon=True).start()

    def show_main_app(self):
        for widget in self.winfo_children():
            widget.destroy()
        
        self.main_app_frame = MainApplicationFrame(
            self, 
            self.api_client, 
            on_logout_callback=self.show_login, 
            sync_callback=self.resync_data
        )
        self.main_app_frame.pack(fill="both", expand=True)

    def resync_data(self):
        sync_window = SyncWindow(self, total_steps=len(ENDPOINTS_TO_SYNC) + 1)
        
        def sync_worker():
            try:
                for endpoint in ENDPOINTS_TO_SYNC:
                    self.api_client.sync_endpoint(endpoint, progress_callback=sync_window.update_progress)
                
                # Полная синхронизация реестра
                self.api_client.sync_pending_registries(progress_callback=sync_window.update_progress)
                
                sync_window.update_progress("Синхронизация завершена.")
                sync_window.finish()
                
                if self.main_app_frame:
                    self.after(0, self.main_app_frame.reload_all_tables)
            except Exception as e:
                sync_window.finish()
                self.after(0, lambda: messagebox.showerror("Ошибка", f"Ошибка синхронизации: {e}"))
        
        threading.Thread(target=sync_worker, daemon=True).start()

if __name__ == "__main__":
    app = App()
    app.mainloop()
