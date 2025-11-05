# tabs.py

import customtkinter as ctk
from tkinter import ttk, messagebox
from form_window import DataFormWindow

class DataTable(ctk.CTkFrame):
    def __init__(self, master, api_client, endpoint, columns, sync_callback, can_edit=True):
        super().__init__(master, fg_color="transparent")
        self.api_client = api_client
        self.endpoint = endpoint
        self.columns = columns
        self.can_edit = can_edit
        self.all_data = []
        self.sync_callback = sync_callback # <== ИЗМЕНЕНО: Сохраняем колбэк

        # --- Панель управления ---
        self.control_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.control_frame.pack(fill="x", pady=5)
        
        # ИЗМЕНЕНО: Кнопка теперь вызывает переданный колбэк
        self.sync_button = ctk.CTkButton(self.control_frame, text="Синхронизировать", command=self.sync_data)
        self.sync_button.pack(side="left")

        if self.can_edit:
            self.add_button = ctk.CTkButton(self.control_frame, text="Добавить", command=self.add_item)
            self.add_button.pack(side="left", padx=10)
        
        self.search_entry = ctk.CTkEntry(self.control_frame, placeholder_text="Поиск...")
        self.search_entry.pack(side="right", padx=5)
        self.search_entry.bind("<KeyRelease>", self.filter_data)

        # --- Стили и таблица ---
        style = ttk.Style()
        style.configure("Treeview", background="#FFFFFF", foreground="#333333", fieldbackground="#FFFFFF", borderwidth=0)
        style.map('Treeview', background=[('selected', '#347083')])
        style.configure("Dark.Treeview", background="#2B2B2B", foreground="#DCE4EE", fieldbackground="#2B2B2B", borderwidth=0)
        style.map('Dark.Treeview', background=[('selected', '#347083')])
        current_style = "Dark.Treeview" if ctk.get_appearance_mode() == "Dark" else "Treeview"

        tree_columns = ["#"] + list(self.columns.keys())
        self.tree = ttk.Treeview(self, columns=tree_columns, show='headings', style=current_style)

        self.sort_directions = {}
        self.tree.heading("#", text="#", command=lambda: self.sort_by_column("#", True))
        self.tree.column("#", width=50, anchor='center', stretch=False)
        for api_field, header_text in self.columns.items():
            self.tree.heading(api_field, text=header_text, command=lambda c=api_field: self.sort_by_column(c))
            self.tree.column(api_field, width=150, anchor='w')

        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)

        self.tree.bind("<Double-1>", self.on_double_click)
        
        # Сразу отображаем данные из локального кэша
        self.all_data = self.api_client.get_local_data(self.endpoint)
        self.display_local_data()

    def sync_data(self):
        """Вызывает глобальную функцию синхронизации."""
        self.sync_callback()

    # ... (остальные методы DataTable остаются без изменений) ...
    def display_local_data(self, data_source=None):
        for item in self.tree.get_children(): self.tree.delete(item)
        data_to_display = data_source if data_source is not None else self.all_data
        for idx, item in enumerate(data_to_display, start=1):
            row_values = [idx]
            for api_field in self.columns.keys():
                value = item.get(api_field)
                if api_field == 'status' and value:
                    status_map = {"approved": "Активен", "pending": "На рассмотрении", "rejected": "Отклонен"}
                    display_value = status_map.get(value, value)
                elif self.endpoint == 'podryads' and api_field in ['drivers', 'cars']:
                    display_value = len(value) if value else 0
                else:
                    display_value = value if value is not None else ""
                row_values.append(display_value)
            self.tree.insert("", "end", values=row_values, iid=item.get('id'))
            
    def sort_by_column(self, col, is_numeric=False):
        direction = self.sort_directions.get(col, False)
        data = []
        for iid in self.tree.get_children(''):
            col_index = self.tree["columns"].index(col)
            val = self.tree.item(iid)['values'][col_index]
            if is_numeric:
                try: val = int(val)
                except ValueError: val = 0
            data.append((val, iid))
        data.sort(reverse=direction)
        for index, (val, iid) in enumerate(data):
            self.tree.move(iid, '', index)
        self.sort_directions[col] = not direction
        
    def filter_data(self, event):
        query = self.search_entry.get().lower()
        if not query:
            self.display_local_data(); return
        filtered_data = []
        for item in self.all_data:
            for value in item.values():
                if query in str(value).lower():
                    filtered_data.append(item); break
        self.display_local_data(filtered_data)
        
    def add_item(self):
        if not self.can_edit: return
        DataFormWindow(master=self, api_client=self.api_client, endpoint=self.endpoint, columns=self.columns, on_save_callback=self.sync_data)
        
    def on_double_click(self, event):
        selected_iid = self.tree.focus()
        if not selected_iid: return
        if self.endpoint == 'podryads':
            self.show_podryad_details(selected_iid); return
        if not self.can_edit:
            messagebox.showinfo("Информация", "Редактирование для этого раздела отключено."); return
        item_data = next((item for item in self.all_data if str(item.get('id')) == str(selected_iid)), None)
        if item_data:
            DataFormWindow(master=self, api_client=self.api_client, endpoint=self.endpoint, columns=self.columns, on_save_callback=self.sync_data, item_data=item_data)
        else:
            messagebox.showerror("Ошибка", "Не удалось найти данные в локальном кэше.")
            
    def show_podryad_details(self, podryad_id):
        podryad_data = next((p for p in self.all_data if str(p.get('id')) == str(podryad_id)), None)
        if not podryad_data: return
        all_drivers = self.api_client.get_local_data('drivers'); all_cars = self.api_client.get_local_data('cars')
        all_markas = {m['id']: m['name'] for m in self.api_client.get_local_data('car-markas')}
        all_models = {m['id']: m['name'] for m in self.api_client.get_local_data('car-models')}
        top = ctk.CTkToplevel(self); top.title(f"Детали: {podryad_data.get('org_name')}"); top.geometry("700x500"); top.transient(self.master); top.grab_set()
        textbox = ctk.CTkTextbox(top, wrap="word", font=("Consolas", 12)); textbox.pack(fill="both", expand=True, padx=10, pady=10)
        details_text = f"Подрядчик: {podryad_data.get('org_name')}\n" + "="*40 + "\n\n"
        driver_ids = podryad_data.get('drivers', [])
        if not driver_ids: details_text += "Водители не прикреплены."
        else:
            details_text += "ВОДИТЕЛИ:\n"
            for driver_id in driver_ids:
                driver = next((d for d in all_drivers if d['id'] == driver_id), None)
                if not driver: continue
                details_text += f"\n- {driver.get('full_name')}:\n"
                car_ids = driver.get('cars', [])
                if not car_ids: details_text += "  (ТС не прикреплены)\n"
                else:
                    for car_id in car_ids:
                        car = next((c for c in all_cars if c['id'] == car_id), None)
                        if not car: continue
                        marka = all_markas.get(car.get('marka'), ''); model = all_models.get(car.get('model'), '')
                        number_pr = f" (пр: {car.get('number_pr')})" if car.get('number_pr') else ""
                        details_text += f"  - {marka} {model} {car.get('number')} {number_pr}\n"
        textbox.insert("1.0", details_text); textbox.configure(state="disabled")

class MainApplicationFrame(ctk.CTkFrame):
    def __init__(self, master, api_client, on_logout_callback, sync_callback):
        super().__init__(master, fg_color="transparent")
        self.api_client = api_client
        self.on_logout = on_logout_callback
        self.sync_callback = sync_callback
        self.tab_view = ctk.CTkTabview(self, anchor="w")
        self.tab_view.pack(fill="both", expand=True)

        self.tab_view.add("Реестр")
        self.tab_view.add("Водители")
        self.tab_view.add("Подрядчики")
        self.tab_view.add("Настройки")

        self.create_registry_tab(self.tab_view.tab("Реестр"))
        self.create_drivers_tab(self.tab_view.tab("Водители"))
        self.create_contractors_tab(self.tab_view.tab("Подрядчики"))
        self.create_settings_tab(self.tab_view.tab("Настройки"))

    # ИЗМЕНЕНО: Добавлен недостающий метод
    def reload_all_tables(self):
        """Проходит по всем вкладкам и обновляет данные в таблицах."""
        for tab_name in self.tab_view._name_list:
            tab_frame = self.tab_view.tab(tab_name)
            if tab_frame.winfo_children() and isinstance(tab_frame.winfo_children()[0], DataTable):
                table = tab_frame.winfo_children()[0]
                table.all_data = table.api_client.get_local_data(table.endpoint)
                table.display_local_data()

    def create_registry_tab(self, tab):
        columns = {'id': 'ID', 'numberPL': '№ ПЛ', 'dataPOPL': 'Дата выдачи', 'tonn': 'Тонн', 'status': 'Статус платежа'}
        DataTable(tab, self.api_client, 'registries', columns, self.sync_callback, can_edit=True).pack(fill="both", expand=True)

    def create_drivers_tab(self, tab):
        columns = {'full_name': 'ФИО', 'birth_date': 'Дата рождения', 'phone_1': 'Телефон', 'status': 'Статус'}
        DataTable(tab, self.api_client, 'drivers', columns, self.sync_callback, can_edit=False).pack(fill="both", expand=True)

    def create_contractors_tab(self, tab):
        columns = {'org_name': 'Название', 'full_name': 'Руководитель', 'inn': 'ИНН', 'drivers': 'Водители', 'cars': 'ТС'}
        DataTable(tab, self.api_client, 'podryads', columns, self.sync_callback, can_edit=False).pack(fill="both", expand=True)
        
    def create_settings_tab(self, tab):
        logout_button = ctk.CTkButton(tab, text="Выйти", command=self.handle_logout, width=200)
        logout_button.pack(pady=50)
    
    def handle_logout(self):
        self.api_client.logout()
        self.on_logout()