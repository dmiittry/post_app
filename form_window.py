# form_window.py

import customtkinter as ctk
from tkinter import messagebox

class DataFormWindow(ctk.CTkToplevel):
    """
    Универсальное окно для добавления и редактирования записей.
    """
    def __init__(self, master, api_client, endpoint, columns, on_save_callback, item_data=None):
        super().__init__(master)
        self.transient(master) # Окно будет поверх главного
        self.grab_set() # Модальное окно (блокирует взаимодействие с главным)
        
        self.api_client = api_client
        self.endpoint = endpoint
        self.columns = columns
        self.on_save = on_save_callback
        self.item_data = item_data # Данные для редактирования
        self.entries = {}

        # Настройка окна
        self.title("Редактирование записи" if item_data else "Добавление записи")
        self.geometry("500x600")

        # --- Создание полей формы динамически ---
        form_frame = ctk.CTkFrame(self, fg_color="transparent")
        form_frame.pack(pady=20, padx=20, fill="both", expand=True)

        for api_field, header_text in columns.items():
            # ID не редактируем, пропускаем его
            if api_field == 'id':
                continue
            
            label = ctk.CTkLabel(form_frame, text=header_text)
            label.pack(anchor="w")
            
            entry = ctk.CTkEntry(form_frame, width=400)
            entry.pack(anchor="w", fill="x", pady=(0, 10))
            
            # Если это редактирование, заполняем поля данными
            if item_data:
                entry.insert(0, item_data.get(api_field, ""))

            self.entries[api_field] = entry
        
        # --- Кнопки ---
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.pack(pady=10, fill="x")

        self.save_button = ctk.CTkButton(button_frame, text="Сохранить", command=self.save_data)
        self.save_button.pack(side="right", padx=(10, 20))

        self.cancel_button = ctk.CTkButton(button_frame, text="Отмена", fg_color="gray", command=self.destroy)
        self.cancel_button.pack(side="right")
        
        if item_data:
            self.delete_button = ctk.CTkButton(button_frame, text="Удалить", fg_color="red", command=self.delete_data)
            self.delete_button.pack(side="left", padx=(20, 0))


    def save_data(self):
        """Собирает данные из полей и отправляет их в API."""
        payload = {api_field: entry.get() for api_field, entry in self.entries.items()}

        if self.item_data: # Режим редактирования
            item_id = self.item_data.get('id')
            success, result = self.api_client.update_item(self.endpoint, item_id, payload)
        else: # Режим добавления
            success, result = self.api_client.create_item(self.endpoint, payload)

        if success:
            messagebox.showinfo("Успех", "Данные успешно сохранены.")
            self.on_save() # Вызываем колбэк (обновление таблицы)
            self.destroy() # Закрываем окно
        else:
            messagebox.showerror("Ошибка сохранения", f"Не удалось сохранить данные: {result}")
            
    def delete_data(self):
        """Удаляет запись."""
        if not self.item_data:
            return
            
        item_id = self.item_data.get('id')
        if messagebox.askyesno("Подтверждение", f"Вы уверены, что хотите удалить запись с ID {item_id}?"):
            success, result = self.api_client.delete_item(self.endpoint, item_id)
            if success:
                messagebox.showinfo("Успех", "Запись удалена.")
                self.on_save()
                self.destroy()
            else:
                messagebox.showerror("Ошибка удаления", f"Не удалось удалить запись: {result}")
