import os
import json
import threading
import subprocess
import customtkinter as ctk
from tkinter import filedialog, messagebox

# Configuration CustomTkinter
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("green")

class AmbiPlexRover(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("AmbiPlex Rover - Batch Encoder")
        self.geometry("800x600")
        
        self.current_folder = ""
        self.video_files = []
        self.checkboxes = []
        self.is_encoding = False
        self.last_clicked_idx = None
        self.shift_pressed = False
        
        # Track Shift key state globally
        self.bind("<KeyPress-Shift_L>", lambda e: setattr(self, 'shift_pressed', True))
        self.bind("<KeyRelease-Shift_L>", lambda e: setattr(self, 'shift_pressed', False))
        self.bind("<KeyPress-Shift_R>", lambda e: setattr(self, 'shift_pressed', True))
        self.bind("<KeyRelease-Shift_R>", lambda e: setattr(self, 'shift_pressed', False))
        
        # --- UI Layout ---
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # Header
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.grid(row=0, column=0, padx=20, pady=20, sticky="ew")
        self.header_frame.grid_columnconfigure(1, weight=1)
        
        self.title_label = ctk.CTkLabel(self.header_frame, text="AmbiPlex Rover", font=ctk.CTkFont(size=24, weight="bold"))
        self.title_label.grid(row=0, column=0, sticky="w")
        
        self.btn_browse = ctk.CTkButton(self.header_frame, text="Sélectionner un dossier", command=self.browse_folder)
        self.btn_browse.grid(row=0, column=2, padx=10, pady=(0, 10))
        
        self.btn_refresh = ctk.CTkButton(self.header_frame, text="Rafraîchir", command=self.scan_folder, fg_color="transparent", border_width=1)
        self.btn_refresh.grid(row=0, column=3, pady=(0, 10))
        
        # Threads Settings
        self.threads_var = ctk.IntVar(value=0)
        self.threads_slider = ctk.CTkSlider(self.header_frame, from_=0, to=16, number_of_steps=16, variable=self.threads_var, command=self.update_threads_label)
        self.threads_slider.grid(row=1, column=2, padx=10, sticky="ew")
        
        self.threads_label = ctk.CTkLabel(self.header_frame, text="CPU Threads: Auto (Max)")
        self.threads_label.grid(row=1, column=3, sticky="w")
        
        # Load initial config for threads
        config = self.load_config()
        initial_threads = config.get("ffmpeg_threads", 0)
        self.threads_var.set(initial_threads)
        self.update_threads_label(initial_threads)
        
    def update_threads_label(self, val):
        v = int(val)
        if v == 0:
            self.threads_label.configure(text="CPU Threads: Auto (Max)")
        else:
            self.threads_label.configure(text=f"CPU Threads: {v}")
        
        # List Frame
        self.scroll_frame = ctk.CTkScrollableFrame(self)
        self.scroll_frame.grid(row=1, column=0, padx=20, pady=0, sticky="nsew")
        
        self.empty_label = ctk.CTkLabel(self.scroll_frame, text="Veuillez sélectionner un dossier pour commencer.", text_color="gray")
        self.empty_label.pack(pady=50)
        
        # Footer
        self.footer_frame = ctk.CTkFrame(self)
        self.footer_frame.grid(row=2, column=0, padx=20, pady=20, sticky="ew")
        self.footer_frame.grid_columnconfigure(0, weight=1)
        
        self.progress_bar = ctk.CTkProgressBar(self.footer_frame)
        self.progress_bar.grid(row=0, column=0, padx=20, pady=(20, 5), sticky="ew")
        self.progress_bar.set(0)
        
        self.btn_start = ctk.CTkButton(self.footer_frame, text="Lancer le Batch", font=ctk.CTkFont(weight="bold"), command=self.start_batch_thread)
        self.btn_start.grid(row=0, column=1, padx=20, pady=(20, 5))
        
        self.status_label = ctk.CTkLabel(self.footer_frame, text="Prêt", text_color="gray")
        self.status_label.grid(row=1, column=0, columnspan=2, padx=20, pady=(0, 10), sticky="w")
        
    def browse_folder(self):
        folder = filedialog.askdirectory(title="Sélectionner le dossier contenant vos films")
        if folder:
            self.current_folder = folder
            self.scan_folder()
            
    def scan_folder(self):
        if not self.current_folder:
            return
            
        # Clear existing list
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
        self.checkboxes.clear()
        self.video_files.clear()
        
        valid_exts = ['.mkv', '.mp4', '.avi']
        
        try:
            for root, _, files in os.walk(self.current_folder):
                for f in files:
                    if os.path.splitext(f)[1].lower() in valid_exts:
                        full_path = os.path.join(root, f)
                        
                        wled_path = os.path.splitext(full_path)[0] + ".wledsub.lz4"
                        exists = os.path.exists(wled_path)
                        
                        var = ctk.BooleanVar(value=False)
                        
                        color = "#10b981" if exists else "white"
                        rel_path = os.path.relpath(full_path, self.current_folder)
                        text = f"{rel_path} (WLEDSUB existant)" if exists else rel_path
                        
                        idx = len(self.checkboxes)
                        cb = ctk.CTkCheckBox(self.scroll_frame, text=text, variable=var, text_color=color,
                                             command=lambda i=idx: self.on_cb_toggle(i))
                        cb.pack(anchor="w", pady=5, padx=10)
                        
                        self.checkboxes.append((cb, var, full_path))
                        self.video_files.append(full_path)
                        
        except Exception as e:
            messagebox.showerror("Erreur", str(e))
            return
            
        if not self.video_files:
            lbl = ctk.CTkLabel(self.scroll_frame, text="Aucun fichier vidéo trouvé dans ce dossier ou ses sous-dossiers.", text_color="gray")
            lbl.pack(pady=50)
            return
            
    def on_cb_toggle(self, idx):
        if self.shift_pressed and self.last_clicked_idx is not None:
            # Shift-Click detected!
            _, current_var, _ = self.checkboxes[idx]
            target_state = current_var.get()
            
            start = min(self.last_clicked_idx, idx)
            end = max(self.last_clicked_idx, idx)
            
            for i in range(start, end + 1):
                _, v, _ = self.checkboxes[i]
                v.set(target_state)
                
        self.last_clicked_idx = idx

    def load_config(self):
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        if not os.path.exists(config_path):
            return {"leds_top": 64, "leds_side": 36, "led_depth": 8, "ffmpeg_threads": 0}
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except:
            return {"leds_top": 64, "leds_side": 36, "led_depth": 8, "ffmpeg_threads": 0}

    def start_batch_thread(self):
        if self.is_encoding:
            return
            
        selected_files = [path for cb, var, path in self.checkboxes if var.get()]
        if not selected_files:
            messagebox.showinfo("Info", "Aucun fichier sélectionné pour l'encodage.")
            return
            
        self.is_encoding = True
        self.btn_start.configure(state="disabled", text="Encodage en cours...")
        self.btn_browse.configure(state="disabled")
        self.btn_refresh.configure(state="disabled")
        
        for cb, var, path in self.checkboxes:
            cb.configure(state="disabled")
            
        thread = threading.Thread(target=self.batch_worker, args=(selected_files,), daemon=True)
        thread.start()
        
    def batch_worker(self, files):
        config = self.load_config()
        leds_x = config.get("leds_top", 64)
        leds_y = config.get("leds_side", 36)
        depth = config.get("led_depth", 8)
        threads = self.threads_var.get()
        
        bake_script = os.path.join(os.path.dirname(__file__), 'bake.py')
        python_exe = os.path.join(os.path.dirname(__file__), 'venv', 'Scripts', 'python.exe')
        if not os.path.exists(python_exe):
            python_exe = "python"
            
        total = len(files)
        
        for i, file_path in enumerate(files):
            filename = os.path.basename(file_path)
            self.update_status(f"[{i+1}/{total}] Démarrage: {filename}", i / total)
            
            cmd = [
                python_exe, bake_script,
                file_path,
                "--leds-x", str(leds_x),
                "--leds-y", str(leds_y),
                "--depth", str(depth),
                "--threads", str(threads)
            ]
            
            # Hide console window on Windows
            creationflags = 0x08000000 if os.name == 'nt' else 0
            
            # Fix Windows emoji encoding crash (cp1252)
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            
            try:
                process = subprocess.Popen(
                    cmd, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.STDOUT, 
                    text=True, 
                    bufsize=1,
                    creationflags=creationflags,
                    env=env
                )
                
                log_path = os.path.join(os.path.dirname(__file__), "rover_debug.txt")
                with open(log_path, "a", encoding="utf-8") as debug_log:
                    debug_log.write(f"\\n--- LANCEMENT DE BAKE.PY POUR {filename} ---\\n")
                    debug_log.write(f"CMD: {' '.join(cmd)}\\n")
                    for line in process.stdout:
                        debug_log.write(line)
                        if "Progression:" in line:
                            pct = line.split("Progression:")[1].strip()
                            self.update_status(f"[{i+1}/{total}] Encodage: {filename} ({pct})", i / total)
                
                process.wait()
            except Exception as e:
                print(f"Erreur sur {filename}: {e}")
                
        self.update_status("Batch terminé avec succès !", 1.0)
        
        # Re-enable UI
        self.after(0, self.finish_batch)
        
    def update_status(self, text, progress_val):
        self.after(0, lambda: self.status_label.configure(text=text))
        self.after(0, lambda: self.progress_bar.set(progress_val))
        
    def finish_batch(self):
        self.is_encoding = False
        self.btn_start.configure(state="normal", text="Lancer le Batch")
        self.btn_browse.configure(state="normal")
        self.btn_refresh.configure(state="normal")
        self.scan_folder()
        messagebox.showinfo("Terminé", "Le processus de batch est terminé !")

if __name__ == "__main__":
    app = AmbiPlexRover()
    app.mainloop()
