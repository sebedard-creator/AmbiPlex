import os
import queue
import threading
import webbrowser
from dataclasses import replace
import customtkinter as ctk
from tkinter import filedialog, messagebox, ttk

from rover_batch import (DEFAULTS, conflicting_outputs, discover_videos, encode_batch,
                         load_settings, track_path)


ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("green")
BG, SURFACE, BORDER = "#111315", "#22262a", "#35393e"
TEXT, MUTED, BLUE, GREEN = "#f1f3f5", "#b0b7bf", "#78b7ff", "#80d4ac"


class ToolTip:
    def __init__(self, widget, text):
        self.widget, self.text, self.window = widget, text, None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)
        widget.bind("<Button-1>", self.hide, add="+")

    def show(self, _event=None):
        if self.window:
            return
        self.window = ctk.CTkToplevel(self.widget)
        self.window.overrideredirect(True)
        self.window.geometry(f"+{self.widget.winfo_rootx()}+{self.widget.winfo_rooty() + 42}")
        ctk.CTkLabel(self.window, text=self.text, fg_color=SURFACE,
                     corner_radius=4).pack(ipadx=10, ipady=4)

    def hide(self, _event=None):
        if self.window:
            self.window.destroy()
            self.window = None


class AmbiPlexRover(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("AmbiPlex Rover")
        self.geometry("1120x820")
        self.minsize(880, 720)
        self.configure(fg_color=BG)
        self.current_folder = ""
        self.records = {}
        self.states = {}
        self.is_encoding = self.is_scanning = self.closing = False
        self.close_when_done = False
        self.stop_scan = threading.Event()
        self.stop_batch = threading.Event()
        self.events = queue.Queue(maxsize=32)
        self.filter_job = None
        self.filter_generation = 0
        self.filtering = False
        self.pending_config_error = None
        try:
            config = load_settings()
        except (OSError, ValueError, TypeError, OverflowError) as error:
            config = DEFAULTS.copy()
            self.pending_config_error = str(error)
        self.settings = config
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(80, self.poll_events)
        if self.pending_config_error:
            self.after(200, lambda: messagebox.showerror("Configuration", self.pending_config_error, parent=self))

    def frame(self, parent):
        return ctk.CTkFrame(parent, fg_color="transparent", corner_radius=0)

    def label(self, parent, text, **kwargs):
        return ctk.CTkLabel(parent, text=text, text_color=TEXT, **kwargs)

    def button(self, parent, text, command, primary=False, **kwargs):
        return ctk.CTkButton(parent, text=text, command=command, height=36,
                             corner_radius=4, fg_color="#21714e" if primary else SURFACE,
                             hover_color="#29855d" if primary else "#343b42",
                             border_color=BORDER, border_width=1, text_color=TEXT, **kwargs)

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        header = self.frame(self)
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 16))
        header.grid_columnconfigure(0, weight=1)
        self.label(header, "AmbiPlex", font=("Segoe UI", 13)).grid(row=0, column=0, sticky="w")
        self.label(header, "Rover", font=("Segoe UI", 28, "bold")).grid(row=1, column=0, sticky="w")
        self.button(header, "Interface Plex", lambda: webbrowser.open("http://localhost:5777")).grid(row=0, column=1, rowspan=2)

        toolbar = self.frame(self)
        toolbar.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 12))
        toolbar.grid_columnconfigure(2, weight=1)
        self.btn_browse = self.button(toolbar, "Ouvrir un dossier", self.browse_folder)
        self.btn_browse.grid(row=0, column=0, padx=(0, 8))
        self.btn_refresh = self.button(toolbar, "\ue72c", self.scan_folder, width=38,
                                       font=("Segoe MDL2 Assets", 16), state="disabled")
        self.btn_refresh.grid(row=0, column=1, padx=(0, 12))
        self.refresh_tip = ToolTip(self.btn_refresh, "Actualiser le dossier")
        self.folder_entry = ctk.CTkEntry(toolbar, height=36, fg_color=SURFACE, border_color=BORDER,
                                         corner_radius=4, placeholder_text="Aucun dossier")
        self.folder_entry.grid(row=0, column=2, sticky="ew")
        self.folder_entry.configure(state="readonly")

        filters = self.frame(self)
        filters.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 10))
        filters.grid_columnconfigure(0, weight=1)
        self.search = ctk.CTkEntry(filters, placeholder_text="Rechercher un fichier", height=34,
                                   corner_radius=4, fg_color=SURFACE, border_color=BORDER)
        self.search.grid(row=0, column=0, sticky="ew", padx=(0, 12))
        self.search.bind("<KeyRelease>", self.schedule_filter)
        self.view_var = ctk.StringVar(value="Tous")
        self.view_menu = ctk.CTkOptionMenu(filters, variable=self.view_var,
                                          values=["Tous", "Sans piste", "Avec piste", "En erreur"],
                                          command=self.schedule_filter, fg_color=SURFACE, button_color=BORDER,
                                          button_hover_color="#4a5057", corner_radius=4, height=34)
        self.view_menu.grid(row=0, column=1)
        selection = self.frame(filters)
        selection.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        selection.grid_columnconfigure(3, weight=1)
        self.select_buttons = []
        for i, (title, mode) in enumerate([("Tout sélectionner", "all"), ("Pistes manquantes", "missing"), ("Désélectionner", "none")]):
            button = self.button(selection, title, lambda m=mode: self.select_files(m), width=136)
            button.grid(row=0, column=i, padx=(0, 8))
            self.select_buttons.append(button)
        self.count_label = self.label(selection, "0 fichier · 0 sélection", anchor="e", font=("Segoe UI", 12))
        self.count_label.grid(row=0, column=3, sticky="ew")

        table_frame = self.frame(self)
        table_frame.grid(row=3, column=0, sticky="nsew", padx=24)
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(0, weight=1)
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Rover.Treeview", background=BG, fieldbackground=BG, foreground=TEXT,
                        borderwidth=0, bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER,
                        rowheight=32, font=("Segoe UI", 11))
        style.configure("Rover.Treeview.Heading", background=SURFACE, foreground=MUTED,
                        relief="flat", font=("Segoe UI", 10, "bold"), padding=(10, 8))
        style.map("Rover.Treeview", background=[("selected", "#24463a")], foreground=[("selected", TEXT)])
        style.map("Rover.Treeview.Heading", background=[("active", BORDER)])
        self.table = ttk.Treeview(table_frame, columns=("file", "track", "status"), show="headings",
                                  selectmode="extended", style="Rover.Treeview")
        for key, title, width, minimum in [("file", "Fichier", 620, 320), ("track", "Piste WLED", 130, 100), ("status", "État", 150, 130)]:
            self.table.heading(key, text=title, anchor="w")
            self.table.column(key, width=width, minwidth=minimum, stretch=key == "file", anchor="w")
        self.table.grid(row=0, column=0, sticky="nsew")
        self.table.tag_configure("ready", foreground=GREEN)
        self.table.tag_configure("error", foreground="#ffa4a4")
        self.table.tag_configure("active", foreground=BLUE)
        vertical = ctk.CTkScrollbar(table_frame, command=self.table.yview)
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal = ctk.CTkScrollbar(table_frame, orientation="horizontal", command=self.table.xview)
        horizontal.grid(row=1, column=0, sticky="ew")
        self.table.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.table.bind("<<TreeviewSelect>>", lambda _e: self.update_count())
        self.table.bind("<Control-a>", self.select_all_key)
        self.empty_label = self.label(table_frame, "Aucun dossier sélectionné", font=("Segoe UI", 14))
        self.empty_label.place(relx=0.5, rely=0.5, anchor="center")

        bottom = self.frame(self)
        bottom.grid(row=4, column=0, sticky="ew", padx=24, pady=(12, 18))
        bottom.grid_columnconfigure(0, weight=1)
        controls = self.frame(bottom)
        controls.grid(row=0, column=0, sticky="ew")
        controls.grid_columnconfigure(1, weight=1)
        self.threads_label = self.label(controls, "", width=148, anchor="w")
        self.threads_label.grid(row=0, column=0)
        self.threads_var = ctk.IntVar(value=self.settings["ffmpeg_threads"])
        thread_max = max(16, os.cpu_count() or 1, self.threads_var.get())
        self.threads_slider = ctk.CTkSlider(controls, from_=0, to=thread_max, number_of_steps=thread_max,
                                            variable=self.threads_var, command=self.update_threads_label,
                                            progress_color="#45b882", button_color="#45b882")
        self.threads_slider.grid(row=0, column=1, sticky="ew", padx=(0, 20))
        self.update_threads_label(self.threads_var.get())
        self.btn_stop = self.button(controls, "Arrêter après ce fichier", self.request_stop, state="disabled", width=170)
        self.btn_stop.grid(row=0, column=2, padx=(0, 8))
        self.btn_start = self.button(controls, "Lancer le lot", self.start_batch_thread, primary=True, state="disabled")
        self.btn_start.grid(row=0, column=3)
        self.settings_label = self.label(bottom, "", anchor="w", font=("Segoe UI", 12))
        self.settings_label.grid(row=1, column=0, sticky="ew", pady=(8, 6))
        self.update_settings_label()
        self.progress_bar = ctk.CTkProgressBar(bottom, height=6, progress_color="#45b882", fg_color=SURFACE)
        self.progress_bar.grid(row=2, column=0, sticky="ew")
        self.progress_bar.set(0)
        self.status_label = self.label(bottom, "Prêt", anchor="w", height=48)
        self.status_label.grid(row=3, column=0, sticky="ew", pady=(4, 0))
        bottom.bind("<Configure>", self.resize_status)
        self.log = ctk.CTkTextbox(bottom, height=112, corner_radius=4, border_width=1, border_color=BORDER,
                                  fg_color="#191c1f", text_color=MUTED, font=("Consolas", 12), wrap="word")
        self.log.grid(row=4, column=0, sticky="ew", pady=(6, 0))
        self.log.configure(state="disabled")

    def resize_status(self, event):
        width = max(200, event.width - 8)
        if self.status_label.cget("wraplength") != width:
            self.status_label.configure(wraplength=width)

    def update_threads_label(self, value):
        count = int(value)
        self.threads_label.configure(text=f"Threads : {count}" if count else "Threads : Auto")

    def update_settings_label(self):
        s = self.settings
        self.settings_label.configure(text=f"LED haut / bas : {s['leds_top']}    ·    LED côtés : {s['leds_side']}    ·    Profondeur : {s['led_depth']} %")

    def append_log(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        # Keep memory and redraw cost bounded during long batches.
        lines = int(self.log.index("end-1c").split(".")[0])
        if lines > 201:
            self.log.delete("1.0", f"{lines - 200}.0")
        self.log.see("end")
        self.log.configure(state="disabled")

    def emit(self, kind, payload):
        while not self.closing:
            try:
                self.events.put((kind, payload), timeout=0.1)
                return
            except queue.Full:
                continue

    def browse_folder(self):
        if self.is_encoding or self.is_scanning:
            return
        folder = filedialog.askdirectory(parent=self, title="Dossier de vidéos", initialdir=self.current_folder or None)
        if folder:
            self.current_folder = folder
            self.folder_entry.configure(state="normal")
            self.folder_entry.delete(0, "end")
            self.folder_entry.insert(0, folder)
            self.folder_entry.configure(state="readonly")
            self.scan_folder()

    def scan_folder(self):
        if not self.current_folder or self.is_encoding or self.is_scanning:
            return
        self.is_scanning = True
        self.filter_generation += 1
        self.filtering = False
        if self.filter_job:
            self.after_cancel(self.filter_job)
            self.filter_job = None
        self.stop_scan.clear()
        self.records.clear()
        self.states.clear()
        self.table.delete(*self.table.get_children())
        self.empty_label.configure(text="Analyse du dossier…")
        self.empty_label.place(relx=0.5, rely=0.5, anchor="center")
        self.status_label.configure(text="Analyse du dossier…")
        self.progress_bar.configure(mode="indeterminate")
        self.progress_bar.start()
        self.set_controls()
        threading.Thread(target=self.scan_worker, args=(self.current_folder,), daemon=True).start()

    def scan_worker(self, folder):
        batch, errors = [], []
        try:
            for record in discover_videos(folder, self.stop_scan, lambda error: errors.append(str(error))):
                batch.append(record)
                if len(batch) == 200:
                    self.emit("scan_rows", batch)
                    batch = []
            if batch:
                self.emit("scan_rows", batch)
        except Exception as error:
            errors.append(str(error))
        self.emit("scan_done", errors)

    def row_values(self, key):
        record = self.records[key]
        return (record.relative, "Existante" if record.has_track else "Manquante", self.states.get(key, "Prêt"))

    def row_tags(self, key):
        state = self.states.get(key, "")
        return ("error",) if state == "Erreur" else ("active",) if state == "En cours" else ("ready",) if self.records[key].has_track else ()

    def matches(self, record, query, view):
        return (query in record.relative.casefold() and
                (view == "Tous" or view == "Sans piste" and not record.has_track or
                 view == "Avec piste" and record.has_track or
                 view == "En erreur" and self.states.get(record.path) == "Erreur"))

    def schedule_filter(self, _event=None):
        if self.is_encoding or self.is_scanning:
            return
        if self.filter_job:
            self.after_cancel(self.filter_job)
        self.filter_job = self.after(180, self.apply_filter)

    def apply_filter(self):
        self.filter_job = None
        if self.is_encoding or self.is_scanning:
            return
        self.filter_generation += 1
        generation = self.filter_generation
        self.filtering = True
        selected = set(self.table.selection())
        self.table.delete(*self.table.get_children())
        query, view = self.search.get().casefold().strip(), self.view_var.get()
        records = iter(self.records.items())
        self.set_controls()

        def insert_chunk():
            if self.closing or generation != self.filter_generation:
                return
            for _ in range(200):
                try:
                    key, record = next(records)
                except StopIteration:
                    self.filtering = False
                    self.update_count()
                    self.set_controls()
                    return
                if self.matches(record, query, view):
                    self.table.insert("", "end", iid=key, values=self.row_values(key), tags=self.row_tags(key))
                    if key in selected:
                        self.table.selection_add(key)
            self.after(1, insert_chunk)

        insert_chunk()

    def select_all_key(self, _event):
        self.select_files("all")
        return "break"

    def select_files(self, mode):
        if self.is_scanning or self.is_encoding or self.filtering:
            return
        visible = self.table.get_children()
        chosen = visible if mode == "all" else [key for key in visible if not self.records[key].has_track] if mode == "missing" else []
        self.table.selection_set(chosen)
        self.update_count()

    def update_count(self):
        visible = len(self.table.get_children())
        selected = len(self.table.selection())
        self.count_label.configure(text=f"{visible}/{len(self.records)} fichiers · {selected} sélection(s)")
        self.btn_start.configure(state="normal" if selected and not (self.is_encoding or self.is_scanning or self.filtering) else "disabled")
        if visible:
            self.empty_label.place_forget()
        elif not self.is_scanning:
            self.empty_label.configure(text="Aucun résultat" if self.records else "Aucune vidéo" if self.current_folder else "Aucun dossier sélectionné")
            self.empty_label.place(relx=0.5, rely=0.5, anchor="center")

    def set_controls(self):
        busy = self.is_encoding or self.is_scanning
        state = "disabled" if busy else "normal"
        for control in [self.btn_browse, self.threads_slider, self.search, self.view_menu]:
            control.configure(state=state)
        for button in self.select_buttons:
            button.configure(state="disabled" if busy or self.filtering else "normal")
        self.btn_refresh.configure(state="normal" if self.current_folder and not busy else "disabled")
        self.table.configure(selectmode="none" if busy or self.filtering else "extended")
        self.btn_stop.configure(state="normal" if self.is_encoding and not self.stop_batch.is_set() else "disabled")
        self.update_count()

    def start_batch_thread(self):
        if self.is_encoding or self.is_scanning or self.filtering:
            return
        selected = list(self.table.selection())
        if not selected:
            return
        if conflicting_outputs(selected):
            messagebox.showerror("Sortie partagée", "Plusieurs vidéos sélectionnées ont le même nom sans extension dans un même dossier. Sélectionnez une seule version de chaque vidéo.", parent=self)
            return
        existing = sum(track_path(path).exists() for path in selected)
        if existing and not messagebox.askyesno("Remplacer les pistes", f"{existing} piste(s) existent déjà. Les régénérer ?", parent=self):
            return
        try:
            self.settings = load_settings()
        except (OSError, ValueError, TypeError, OverflowError) as error:
            messagebox.showerror("Configuration", str(error), parent=self)
            return
        # Snapshot Tk values on the UI thread before starting the worker.
        settings = {**self.settings, "ffmpeg_threads": self.threads_var.get()}
        self.update_settings_label()
        self.stop_batch.clear()
        self.is_encoding = True
        self.progress_bar.set(0)
        for path in selected:
            self.states[path] = "En attente"
            self.table.item(path, values=self.row_values(path), tags=self.row_tags(path))
        self.append_log(f"Lot lancé : {len(selected)} fichier(s).")
        self.set_controls()
        threading.Thread(target=encode_batch, args=(selected, settings, self.stop_batch, self.emit), daemon=True).start()

    def request_stop(self):
        if self.is_encoding:
            self.stop_batch.set()
            self.btn_stop.configure(state="disabled")
            self.append_log("Arrêt demandé : le fichier courant sera terminé, les suivants ne seront pas lancés.")

    def poll_events(self):
        if self.closing:
            return
        for _ in range(32):
            try:
                kind, payload = self.events.get_nowait()
            except queue.Empty:
                break
            self.handle_event(kind, payload)
            if self.closing:
                return
            if kind == "scan_rows":
                break
        self.after(10 if self.is_scanning else 80, self.poll_events)

    def handle_event(self, kind, payload):
        if kind == "scan_rows":
            query, view = self.search.get().casefold().strip(), self.view_var.get()
            for record in payload:
                self.records[record.path] = record
                if self.matches(record, query, view):
                    self.table.insert("", "end", iid=record.path, values=self.row_values(record.path), tags=self.row_tags(record.path))
            self.update_count()
        elif kind == "scan_done":
            self.is_scanning = False
            self.progress_bar.stop()
            self.progress_bar.configure(mode="determinate")
            self.progress_bar.set(0)
            self.status_label.configure(text=f"{len(self.records)} vidéo(s) trouvée(s)" + (f" · {len(payload)} erreur(s) de lecture" if payload else ""))
            for error in payload:
                self.append_log(error)
            self.set_controls()
        elif kind == "log":
            self.append_log(payload)
        elif kind == "started":
            path, index, total = payload
            self.states[path] = "En cours"
            self.table.item(path, values=self.row_values(path), tags=self.row_tags(path))
            self.table.see(path)
            self.status_label.configure(text=f"[{index + 1}/{total}] {os.path.basename(path)}")
            self.append_log(f"[{index + 1}/{total}] {self.records[path].relative}")
        elif kind == "progress":
            path, index, total, percent, line = payload
            self.progress_bar.set((index + percent / 100) / total)
            self.status_label.configure(text=f"[{index + 1}/{total}] {os.path.basename(path)} · {line}")
            self.table.set(path, "status", f"{percent:.1f} %")
        elif kind == "file_done":
            path, success, error, completed, total = payload
            self.states[path] = "Terminé" if success else "Erreur"
            if success:
                self.records[path] = replace(self.records[path], has_track=True)
            self.table.item(path, values=self.row_values(path), tags=self.row_tags(path))
            self.progress_bar.set(completed / total)
            self.append_log(f"{'Terminé' if success else 'Erreur'} : {self.records[path].relative}" + (f" · {error}" if error else ""))
        elif kind == "batch_done":
            succeeded, failed, pending = payload
            self.is_encoding = False
            for path, state in self.states.items():
                if state == "En attente":
                    self.states[path] = "Non traité"
                    if self.table.exists(path):
                        self.table.set(path, "status", "Non traité")
            summary = f"{succeeded} réussi(s) · {failed} erreur(s) · {pending} non traité(s)"
            self.status_label.configure(text=summary)
            self.append_log(summary)
            self.set_controls()
            self.apply_filter()
            if self.close_when_done:
                self.on_close()

    def on_close(self):
        if self.is_encoding:
            if messagebox.askyesno("Encodage en cours", "Terminer le fichier courant, puis fermer Rover sans lancer les suivants ?", parent=self):
                self.close_when_done = True
                self.request_stop()
            return
        self.closing = True
        self.stop_scan.set()
        self.refresh_tip.hide()
        self.destroy()


if __name__ == "__main__":
    app = AmbiPlexRover()
    app.mainloop()
