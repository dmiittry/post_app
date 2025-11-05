# main.py

import customtkinter as ctk
import threading
from tkinter import messagebox

from login import LoginFrame
from tabs import MainApplicationFrame, DataTable
from api_client import APIClient
from sync_window import SyncWindow
import requests 

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

ENDPOINTS_TO_SYNC = [
    "podryads", "ie-profiles", "cars", "car-markas", "car-models", 
    "drivers", "registries", "seasons", "gruzes", "loading-points", 
    "unloading-points", "organizations", "customers", "cargo-batches"
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
        self.main_frame = None
        
        self.after(100, self.attempt_auto_login)

    def attempt_auto_login(self):
        success, message = self.api_client.try_auto_login()
        if success:
            self.show_main_application(run_sync_on_start=True)
        else:
            self.show_login_window()

    def show_login_window(self, re_auth_for_sync=False):
        for widget in self.winfo_children(): widget.destroy()
        self.login_frame = LoginFrame(self, self.handle_login_attempt)
        if re_auth_for_sync:
            self.login_frame.status_label.configure(text="Для синхронизации требуется онлайн-аутентификация.", text_color="orange")
        self.login_frame.pack(fill="both", expand=True, padx=20, pady=20)

    def handle_login_attempt(self, username, password, remember):
        success, message = self.api_client.login(username, password, remember)
        if success:
            # После первого успешного входа всегда запускаем синхронизацию
            self.show_main_application(run_sync_on_start=True)
        else:
            self.login_frame.show_error(message)

    def show_main_application(self, run_sync_on_start=False):
        for widget in self.winfo_children(): widget.destroy()
        self.main_frame = MainApplicationFrame(
            self, 
            self.api_client, 
            on_logout_callback=self.handle_logout, 
            sync_callback=self.sync_all_data
        )
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        if run_sync_on_start:
            self.after(200, self.sync_all_data) # Небольшая задержка, чтобы окно успело отрисоваться

    def handle_logout(self):
        self.api_client.logout()
        self.show_login_window()

    def sync_all_data(self):
        if not self.api_client.is_network_ready():
            self.show_login_window(re_auth_for_sync=True)
            return
        
        sync_win = SyncWindow(self, total_steps=len(ENDPOINTS_TO_SYNC))
        threading.Thread(target=self._sync_thread_worker, args=(sync_win,), daemon=True).start()

    def _sync_thread_worker(self, sync_win):
        print("Начало полной синхронизации данных...")
        
        # Оборачиваем весь цикл в try...except
        try:
            for endpoint in ENDPOINTS_TO_SYNC:
                # Проверка аутентификации на первом шаге
                if endpoint == ENDPOINTS_TO_SYNC[0]:
                    url = f"{self.api_client.base_url}{endpoint}/"
                    response = self.api_client.session.get(url, timeout=10)
                    if response.status_code in [401, 403]:
                        print("Ошибка аутентификации при синхронизации.")
                        self.after(0, sync_win.destroy)
                        self.after(0, lambda: self.show_login_window(re_auth_for_sync=True))
                        return
                    # Если все ок, обрабатываем уже полученные данные
                    self.api_client.cache.compare_and_update(endpoint, response.json())
                    # Обновляем UI из основного потока
                    self.after(0, lambda: sync_win.update_progress(f"Загрузка: {endpoint}..."))
                    continue
                
                # Для остальных эндпоинтов
                self.api_client.sync_endpoint(endpoint, progress_callback=lambda msg: self.after(0, sync_win.update_progress, msg))
            
            print("Синхронизация завершена.")
            self.after(0, self.on_sync_finished, sync_win)

        except requests.exceptions.RequestException as e:
            print(f"Ошибка сети: {e}")
            self.after(0, sync_win.destroy)
            # ИЗМЕНЕНО: Правильно передаем переменную 'e' в lambda
            self.after(0, lambda err=e: messagebox.showerror("Ошибка сети", f"Не удалось подключиться к серверу:\n{err}"))
            return

    def on_sync_finished(self, sync_win):
        sync_win.finish()
        if self.main_frame:
            self.main_frame.reload_all_tables()

if __name__ == "__main__":
    app = App()
    app.mainloop()
