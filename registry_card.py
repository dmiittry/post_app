# registry_card.py

import customtkinter as ctk
from tkinter import messagebox
from tkcalendar import DateEntry
from datetime import datetime

class RegistryCardWindow(ctk.CTkToplevel):
    """
    Карточка реестра с редактируемыми полями и удалением.
    """
    def __init__(self, master, api_client, record: dict, on_saved_callback=None):
        super().__init__(master)
        self.title(f"Реестр: {record.get('numberPL') or record.get('id')}")
        self.geometry("760x740")
        self.transient(master)
        self.grab_set()

        self.api_client = api_client
        self.record = record
        self.on_saved = on_saved_callback

        self.fields = {}
        self.field_order = []

        self.related = {
            "drivers": api_client.get_local_data('drivers') or [],
            "cars": api_client.get_local_data('cars') or [],
            "podryads": api_client.get_local_data('podryads') or [],
            "gruzes": api_client.get_local_data('gruzes') or [],
        }
        self.by_id = {
            "drivers": {d.get('id'): d for d in self.related['drivers'] if isinstance(d, dict)},
            "cars": {c.get('id'): c for c in self.related['cars'] if isinstance(c, dict)},
            "podryads": {p.get('id'): p for p in self.related['podryads'] if isinstance(p, dict)},
            "gruzes": {g.get('id'): g for g in self.related['gruzes'] if isinstance(g, dict)},
        }

        self.content = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.content.pack(fill="both", expand=True, padx=12, pady=12)
        self.content.grid_columnconfigure(0, weight=0)
        self.content.grid_columnconfigure(1, weight=1)

        self._build_form()
        self._prefill()
        self._build_footer()

    # ---------- UI ----------
    def _build_form(self):
        row = 0

        def add_label(r, text):
            ctk.CTkLabel(self.content, text=text, anchor="w").grid(row=r, column=0, sticky="w", padx=(4, 8), pady=5)

        def bind_enter(widget, key):
            widget.bind("<Return>", lambda e, k=key: self._focus_next(k))

        def add_entry(r, key, placeholder=""):
            add_label(r, self._label_for(key))
            w = ctk.CTkEntry(self.content, placeholder_text=placeholder)
            w.grid(row=r, column=1, sticky="ew", padx=(0, 8), pady=5)
            self.fields[key] = w
            self.field_order.append(key)
            bind_enter(w, key)

        def add_combo(r, key, values):
            add_label(r, self._label_for(key))
            w = ctk.CTkComboBox(self.content, values=values, state="readonly")
            w.grid(row=r, column=1, sticky="ew", padx=(0, 8), pady=5)
            self.fields[key] = w
            self.field_order.append(key)
            bind_enter(w, key)

        def add_datetime(r, key):
            add_label(r, self._label_for(key))
            row_frame = ctk.CTkFrame(self.content, fg_color="transparent")
            row_frame.grid(row=r, column=1, sticky="w", padx=(0, 8), pady=5)
            date_w = DateEntry(row_frame, date_pattern='dd.mm.yyyy', width=12)
            hour_w = ctk.CTkComboBox(row_frame, width=70, values=[f"{h:02d}" for h in range(24)])
            min_w = ctk.CTkComboBox(row_frame, width=70, values=[f"{m:02d}" for m in range(0, 60, 5)])
            date_w.pack(side="left")
            hour_w.pack(side="left", padx=5)
            min_w.pack(side="left")
            self.fields[key] = (date_w, hour_w, min_w)
            self.field_order.append(key)
            date_w.bind("<Return>", lambda e, w=hour_w: w.focus_set())
            hour_w.bind("<Return>", lambda e, w=min_w: w.focus_set())
            min_w.bind("<Return>", lambda e, k=key: self._focus_next(k))

        driver_names = [d.get('full_name','') for d in self.related['drivers']]
        car_numbers = [c.get('number','') for c in self.related['cars']]
        pod_names = [p.get('org_name','') for p in self.related['podryads']]
        gruz_names = [g.get('name','') for g in self.related['gruzes']]

        add_combo(row, "driver", driver_names); row += 1
        add_combo(row, "driver2", driver_names); row += 1
        add_combo(row, "number", car_numbers); row += 1
        add_combo(row, "pod", pod_names); row += 1

        add_entry(row, "marsh", "Код маршрута"); row += 1
        add_entry(row, "numberPL", "Номер ПЛ"); row += 1
        add_combo(row, "gruz", gruz_names); row += 1

        add_datetime(row, "dataPOPL"); row += 1
        add_datetime(row, "dataSDPL"); row += 1

        add_entry(row, "numberTN", "№ ТТН"); row += 1
        add_datetime(row, "loading_time"); row += 1
        add_datetime(row, "unloading_time"); row += 1

        add_entry(row, "tonn", "Тонн (напр. 20.00)"); row += 1
        add_entry(row, "fuel_consumption", "ГСМ, л"); row += 1
        add_entry(row, "dispatch_info", "Отправка"); row += 1
        add_entry(row, "comment", "Комментарий"); row += 1

    def _build_footer(self):
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(side="bottom", fill="x", padx=12, pady=(0, 12))

        # Удалить
        self.delete_btn = ctk.CTkButton(
            btn_frame, text="Удалить", fg_color="#c62828",
            command=self._delete
        )
        self.delete_btn.pack(side="left")

        # Сдали документы
        self.done_btn = ctk.CTkButton(
            btn_frame, text="Сдали документы",
            command=self._mark_received, fg_color="#2e7d32"
        )
        self.done_btn.pack(side="left", padx=8)

        # Сохранить
        btn = ctk.CTkButton(btn_frame, text="Сохранить", height=36, command=self._save)
        btn.pack(side="right")

    # ---------- Helpers ----------
    def _label_for(self, key):
        labels = {
            "driver": "Водитель",
            "driver2": "Второй водитель",
            "number": "ТС",
            "pod": "Подрядчик",
            "marsh": "Маршрут",
            "numberPL": "Номер ПЛ",
            "gruz": "Вид груза",
            "dataPOPL": "Дата выдачи ПЛ",
            "dataSDPL": "Дата сдачи ПЛ",
            "numberTN": "№ ТТН",
            "loading_time": "Время погрузки",
            "unloading_time": "Время разгрузки",
            "tonn": "Количество тонн",
            "fuel_consumption": "Расход ГСМ, л",
            "dispatch_info": "Отправка",
            "comment": "Комментарий",
        }
        return labels.get(key, key)

    def _focus_next(self, key):
        try:
            idx = self.field_order.index(key)
            if idx < len(self.field_order) - 1:
                nxt_key = self.field_order[idx + 1]
                w = self.fields.get(nxt_key)
                if isinstance(w, tuple):
                    w[0].focus_set()
                else:
                    w.focus_set()
        except ValueError:
            pass

    def _prefill(self):
        r = self.record

        def set_combo_from_id(key, rel_key, name_field):
            val_id = r.get(key)
            name = ""
            if val_id and val_id in self.by_id[rel_key]:
                name = self.by_id[rel_key][val_id].get(name_field, "")
            cb = self.fields.get(key)
            if cb:
                cb.set(name or "")

        def set_entry(key):
            w = self.fields.get(key)
            if w:
                w.delete(0, "end")
                w.insert(0, r.get(key) or "")

        def set_datetime(key):
            group = self.fields.get(key)
            iso = r.get(key)
            if group and iso:
                try:
                    dt = datetime.fromisoformat(iso.replace("Z","+00:00")) if "Z" in iso else datetime.fromisoformat(iso)
                    dt = dt.replace(tzinfo=None)
                    group[0].set_date(dt)
                    group[1].set(f"{dt.hour:02d}")
                    group[2].set(f"{(dt.minute // 5) * 5:02d}")
                except Exception:
                    pass

        set_combo_from_id("driver", "drivers", "full_name")
        set_combo_from_id("driver2", "drivers", "full_name")
        set_combo_from_id("number", "cars", "number")
        set_combo_from_id("pod", "podryads", "org_name")
        set_combo_from_id("gruz", "gruzes", "name")

        for k in ["marsh", "numberPL", "numberTN", "tonn", "fuel_consumption", "dispatch_info", "comment"]:
            set_entry(k)

        for k in ["dataPOPL", "dataSDPL", "loading_time", "unloading_time"]:
            set_datetime(k)

    def _collect_payload(self):
        payload = {}

        def get_id_by_name(rel_key, name_field, name_value):
            if not name_value:
                return None
            for item in self.related[rel_key]:
                if item.get(name_field) == name_value:
                    return item.get('id')
            return None

        def read_entry(key):
            w = self.fields.get(key)
            if not w:
                return None
            return w.get().strip()

        def read_datetime(key):
            group = self.fields.get(key)
            if not group:
                return None
            try:
                date_val = group[0].get_date()
                hour = group[1].get()
                minute = group[2].get()
                if not hour or not minute:
                    return None
                dt = datetime(date_val.year, date_val.month, date_val.day, int(hour), int(minute))
                return dt.strftime("%Y-%m-%dT%H:%M:%S")
            except Exception:
                return None

        payload['driver'] = get_id_by_name('drivers', 'full_name', self.fields['driver'].get() if self.fields.get('driver') else "")
        payload['driver2'] = get_id_by_name('drivers', 'full_name', self.fields['driver2'].get() if self.fields.get('driver2') else "")
        payload['number'] = get_id_by_name('cars', 'number', self.fields['number'].get() if self.fields.get('number') else "")
        payload['pod'] = get_id_by_name('podryads', 'org_name', self.fields['pod'].get() if self.fields.get('pod') else "")
        payload['gruz'] = get_id_by_name('gruzes', 'name', self.fields['gruz'].get() if self.fields.get('gruz') else "")

        for k in ["marsh", "numberPL", "numberTN", "dispatch_info", "comment"]:
            val = read_entry(k)
            if val is not None:
                payload[k] = val

        for k in ["tonn", "fuel_consumption"]:
            val = read_entry(k)
            if val:
                payload[k] = str(val)

        for k in ["dataPOPL", "dataSDPL", "loading_time", "unloading_time"]:
            payload[k] = read_datetime(k)

        clean = {k: v for k, v in payload.items() if v not in [None, ""]}
        return clean

    def _save(self):
        item_id = self.record.get('id')
        if not item_id:
            messagebox.showerror("Ошибка", "ID записи не найден.")
            return
        payload = self._collect_payload()
        if not payload:
            messagebox.showinfo("Информация", "Нет изменений для сохранения.")
            return

        ok, resp, code = self.api_client.update_item('registries', item_id, payload, use_patch=True)
        if ok:
            messagebox.showinfo("Успех", "Изменения сохранены.")
            if self.on_saved:
                self.on_saved()
            self.destroy()
        else:
            messagebox.showerror("Ошибка", f"Не удалось сохранить изменения (статус {code}).\n{resp}")

    def _mark_received(self):
        now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        grp = self.fields.get('dataSDPL')
        if isinstance(grp, tuple):
            dt = datetime.now()
            grp[0].set_date(dt)
            grp[1].set(f"{dt.hour:02d}")
            grp[2].set(f"{(dt.minute // 5) * 5:02d}")
        di = self.fields.get('dispatch_info')
        if di:
            di.delete(0, 'end')
            di.insert(0, 'получили')
        item_id = self.record.get('id')
        if not item_id:
            return
        payload = {"dispatch_info": "получили", "dataSDPL": now}
        ok, resp, code = self.api_client.update_item('registries', item_id, payload, use_patch=True)
        if ok:
            messagebox.showinfo("Успех", "Отмечено как «Сдали документы».")
            if self.on_saved:
                self.on_saved()
            self.destroy()
        else:
            messagebox.showerror("Ошибка", f"Не удалось сохранить изменения (статус {code}).\n{resp}")

    def _delete(self):
        item_id = self.record.get('id')
        if not item_id:
            messagebox.showerror("Ошибка", "ID записи не найден.")
            return
        if not messagebox.askyesno("Подтверждение", "Действительно удалить запись?"):
            return
        ok, resp, code = self.api_client.delete_item('registries', item_id)
        if ok:
            messagebox.showinfo("Готово", "Запись удалена.")
            if self.on_saved:
                self.on_saved()
            self.destroy()
        else:
            messagebox.showerror("Ошибка", f"Не удалось удалить (статус {code}).\n{resp}")
