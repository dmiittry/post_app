# sync_window.py

import customtkinter as ctk

class SyncWindow(ctk.CTkToplevel):
    """
    Окно для отображения прогресса синхронизации данных.
    """
    def __init__(self, master, total_steps):
        super().__init__(master)
        self.title("Синхронизация")
        self.geometry("400x150")
        self.transient(master)
        self.grab_set() # Блокируем взаимодействие с главным окном
        self.protocol("WM_DELETE_WINDOW", lambda: None) # Запрещаем закрытие окна

        self.total_steps = total_steps
        self.current_step = 0

        self.label = ctk.CTkLabel(self, text="Подготовка к синхронизации...")
        self.label.pack(pady=(20, 10))

        self.progress_bar = ctk.CTkProgressBar(self, width=350)
        self.progress_bar.set(0)
        self.progress_bar.pack(pady=10)

    def update_progress(self, message):
        """Обновляет текст и прогресс-бар."""
        self.current_step += 1
        progress = self.current_step / self.total_steps
        self.label.configure(text=message)
        self.progress_bar.set(progress)
        self.update_idletasks() # Немедленно обновляем интерфейс

    def finish(self):
        """Завершает процесс и закрывает окно."""
        self.label.configure(text="Синхронизация завершена!")
        self.progress_bar.set(1)
        self.after(1500, self.destroy) # Закрываем окно через 1.5 секунды
