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
        
        self.title("А-Групп: Клиент управления: версия 1.0.1")
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
        
        
        #таймер автосинхронизации (каждые 30 секунд)
        self.auto_sync_interval = 30000  # 30 секунд в миллисекундах
        self.auto_sync_timer = None
        self.start_auto_sync()

    def start_auto_sync(self):
            """Запускает автосинхронизацию реестра"""
            def auto_sync_worker():
                if not self.api_client.is_network_ready():
                    return
                
                try:
                    # Тихая синхронизация только реестра
                    self.api_client.sync_endpoint("registries")
                    
                    # Обновляем таблицу реестра, если она открыта
                    if hasattr(self, 'main_app_frame') and self.main_app_frame:
                        self.after(0, lambda: self.main_app_frame.reload_registry_table() if hasattr(self.main_app_frame, 'reload_registry_table') else None)
                    
                    print("-> Автосинхронизация реестра выполнена")
                except Exception as e:
                    print(f"-> Ошибка автосинхронизации: {e}")
            
            # Запускаем в фоновом потоке
            import threading
            threading.Thread(target=auto_sync_worker, daemon=True).start()
            
            # Планируем следующий запуск
            self.auto_sync_timer = self.after(self.auto_sync_interval, self.start_auto_sync)
        
    def destroy(self):
        """Отменяем таймер при закрытии приложения"""
        if self.auto_sync_timer:
            self.after_cancel(self.auto_sync_timer)
        super().destroy()
            
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
        
        # ИЗМЕНЕНО: прогресс = 2 шага (справочники параллельно + реестр)
        sync_window = SyncWindow(self, total_steps=2)
        
        def sync_data():
            sync_window.update_progress("Загрузка справочников...")
            
            # ИЗМЕНЕНО: Параллельная синхронизация всех справочников
            self.api_client.sync_all_parallel(
                ENDPOINTS_TO_SYNC, 
                progress_callback=sync_window.update_progress,
                max_workers=6  # Можно увеличить до 10 для ещё большей скорости
            )
            
            sync_window.update_progress("Загрузка реестра...")
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
        # ИЗМЕНЕНО: прогресс = 3 шага
        sync_window = SyncWindow(self, total_steps=3)
        
        def sync_worker():
            try:
                sync_window.update_progress("Обновление справочников...")
                
                # Параллельная загрузка
                self.api_client.sync_all_parallel(
                    ENDPOINTS_TO_SYNC, 
                    progress_callback=sync_window.update_progress,
                    max_workers=6
                )
                
                sync_window.update_progress("Отправка локальных изменений...")
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
