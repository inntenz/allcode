import time
import keyboard
import random
import mss
import numpy as np
from PIL import Image
import threading
import customtkinter as ctk
import json
import os

# ═══════════════════════════════════════════════════════════
# CONFIG MANAGEMENT
# ═══════════════════════════════════════════════════════════

CONFIG_FILE = "config.json"

def load_config():
    default_config = {
        "target_fps": 144,
        "tolerance": 55,
        "reaction_time": 0.0,
        "delay_between_shots": 0.4,
        "toggle_key": "f",
        "shoot_key": "7",
        "show_crosshair": True
    }
    
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return config
        except Exception as e:
            print(f"Error: {e}")
    
    save_config(default_config)
    return default_config

def save_config(config_dict):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config_dict, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error: {e}")

# ═══════════════════════════════════════════════════════════
# GLOBALE VARIABLEN
# ═══════════════════════════════════════════════════════════

class Settings:
    def __init__(self):
        config = load_config()
        self.target_fps = config["target_fps"]
        self.tolerance = config["tolerance"]
        self.reaction_time = config["reaction_time"]
        self.delay_between_shots = config["delay_between_shots"]
        self.toggle_key = config["toggle_key"]
        self.shoot_key = config["shoot_key"]
        self.show_crosshair = config.get("show_crosshair", True)
        self.shooting_enabled = False
        self.running = True
    
    def to_dict(self):
        return {
            "target_fps": self.target_fps,
            "tolerance": self.tolerance,
            "reaction_time": self.reaction_time,
            "delay_between_shots": self.delay_between_shots,
            "toggle_key": self.toggle_key,
            "shoot_key": self.shoot_key,
            "show_crosshair": self.show_crosshair
        }
    
    def save(self):
        save_config(self.to_dict())

settings = Settings()
crosshair_window = None

# ═══════════════════════════════════════════════════════════
# CROSSHAIR OVERLAY
# ═══════════════════════════════════════════════════════════

class CrosshairOverlay:
    def __init__(self):
        self.window = ctk.CTkToplevel()
        self.window.withdraw()
        
        self.window.overrideredirect(True)
        self.window.attributes('-topmost', True)
        self.window.attributes('-transparentcolor', 'black')
        self.window.configure(fg_color='black')
        
        self.canvas = ctk.CTkCanvas(self.window, width=8, height=8, 
                                   bg='black', highlightthickness=0)
        self.canvas.pack()
        
        self.canvas.create_rectangle(1, 1, 7, 7, outline='white', width=1)
        
        self.center_on_screen()
        
    def center_on_screen(self):
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            center_x = monitor["left"] + monitor["width"] // 2
            center_y = monitor["top"] + monitor["height"] // 2
            
            self.window.geometry(f"8x8+{center_x-4}+{center_y-4}")
    
    def show(self):
        self.window.deiconify()
        self.window.lift()
        
    def hide(self):
        self.window.withdraw()
    
    def destroy(self):
        try:
            self.window.destroy()
        except:
            pass

# ═══════════════════════════════════════════════════════════
# SHOOTING LOGIC
# ═══════════════════════════════════════════════════════════

def clickkey():
    timeout = random.uniform(0, settings.reaction_time)
    time.sleep(timeout)
    keyboard.press(settings.shoot_key)
    time.sleep(0.0075)
    keyboard.release(settings.shoot_key)

def is_target_red(r, g, b):
    target_r, target_g, target_b = 244, 65, 69
    return (abs(int(r) - target_r) <= settings.tolerance and 
            abs(int(g) - target_g) <= settings.tolerance and 
            abs(int(b) - target_b) <= settings.tolerance)

def check_for_red():
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        center_x = monitor["width"] // 2
        center_y = monitor["height"] // 2
        
        region = {
            "left": monitor["left"] + center_x - 3,
            "top": monitor["top"] + center_y - 3,
            "width": 7,
            "height": 7
        }
        
        screenshot = sct.grab(region)
        img = Image.frombytes("RGB", screenshot.size, screenshot.rgb)
        pixels = np.array(img)
        
        for y in range(7):
            for x in range(7):
                r, g, b = pixels[y, x]
                if is_target_red(r, g, b):
                    return True
        return False

def toggle_shooting():
    global crosshair_window
    settings.shooting_enabled = not settings.shooting_enabled
    
    if crosshair_window and settings.show_crosshair:
        if settings.shooting_enabled:
            crosshair_window.show()
        else:
            crosshair_window.hide()

def monitor_screen():
    while settings.running:
        start_time = time.perf_counter()
        frame_time = 1.0 / settings.target_fps
        
        if settings.shooting_enabled:
            if check_for_red():
                clickkey()
                time.sleep(settings.delay_between_shots)
        
        elapsed = time.perf_counter() - start_time
        sleep_time = max(0, frame_time - elapsed)
        if sleep_time > 0:
            time.sleep(sleep_time)

# ═══════════════════════════════════════════════════════════
# MODERNE GUI MIT CUSTOMTKINTER
# ═══════════════════════════════════════════════════════════

class ShootOnRedGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Cherrys'Pixel")
        
        # Theme Setup
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        # Fenster MIT Standard-Titelleiste für normale Funktionen
        self.root.overrideredirect(False)
        
        # Größe und Position auf 2. Monitor setzen
        self.center_on_second_monitor()
        
        self.create_title_bar()
        self.create_widgets()
        self.update_status_display()
        
    def center_on_second_monitor(self):
        try:
            with mss.mss() as sct:
                monitors = sct.monitors
                
                if len(monitors) > 2:
                    monitor = monitors[2]
                else:
                    monitor = monitors[1]
                
                width = 420
                height = 690
                
                center_x = monitor["left"] + (monitor["width"] - width) // 2
                center_y = monitor["top"] + (monitor["height"] - height) // 2
                
                self.root.geometry(f"{width}x{height}+{center_x}+{center_y}")
        except:
            self.root.geometry("420x690")
    
    def create_title_bar(self):
        title_bar = ctk.CTkFrame(self.root, height=50, corner_radius=0, fg_color="#252525")
        title_bar.pack(fill="x", padx=0, pady=0)
        title_bar.pack_propagate(False)

        title_label = ctk.CTkLabel(title_bar, text="Cherrys'Pixel", 
                                   font=ctk.CTkFont(size=20, weight="bold"),
                                   text_color="#df2a2a")
        title_label.pack(pady=15, padx=20)
        
    def create_widgets(self):
        settings_container = ctk.CTkFrame(self.root, corner_radius=0, fg_color="#252525")
        settings_container.pack(fill="both", expand=True, padx=20, pady=20)
        
        status_frame = ctk.CTkFrame(settings_container, corner_radius=10, fg_color="#252525")
        status_frame.pack(fill="x", pady=8)
        
        status_label_text = ctk.CTkLabel(status_frame, text="Status:", 
                                         font=ctk.CTkFont(size=13))
        status_label_text.pack(side="left", padx=20, pady=15)
        
        self.status_label = ctk.CTkLabel(status_frame, text="INACTIVE", 
                                        font=ctk.CTkFont(size=13, weight="bold"),
                                        text_color="#ff4444")
        self.status_label.pack(side="right", padx=20, pady=15)
        
        # Toggle Key
        self.create_key_setting(settings_container, "Toggle Key", "toggle", 0)
        
        # Shoot Key  
        self.create_key_setting(settings_container, "Shoot Key", "shoot", 1)
        
        # FPS Setting
        self.create_entry_setting(settings_container, "FPS", 
                                 settings.target_fps, self.update_fps, 2)
        
        # Tolerance Setting
        self.create_entry_setting(settings_container, "Red Tolerance", 
                                 settings.tolerance, self.update_tolerance, 3)
        
        # Reaction Time Slider
        self.create_slider_setting(settings_container, "Reaction Time", 
                                  settings.reaction_time, self.update_reaction_time, 4)
        
        # Shot Delay Slider
        self.create_slider_setting(settings_container, "Shot Delay", 
                                  settings.delay_between_shots, self.update_delay, 5)
        
        # Crosshair Toggle
        self.create_switch_setting(settings_container, "Show Crosshair Box", 
                                  settings.show_crosshair, self.toggle_crosshair, 6)
    
    def create_key_setting(self, parent, label_text, key_type, row):
        frame = ctk.CTkFrame(parent, corner_radius=10, fg_color="#1a1a1a")
        frame.pack(fill="x", pady=8)
        
        label = ctk.CTkLabel(frame, text=label_text, font=ctk.CTkFont(size=13))
        label.pack(side="left", padx=20, pady=15)
        
        if key_type == "toggle":
            self.toggle_key_btn = ctk.CTkButton(frame, 
                                               text=settings.toggle_key.upper(),
                                               width=100, height=35, corner_radius=8,
                                               fg_color="#2a2a2a", hover_color="#3a3a3a",
                                               command=self.change_toggle_key)
            self.toggle_key_btn.pack(side="right", padx=20, pady=10)
        else:
            self.shoot_key_btn = ctk.CTkButton(frame, 
                                              text=settings.shoot_key.upper(),
                                              width=100, height=35, corner_radius=8,
                                              fg_color="#2a2a2a", hover_color="#3a3a3a",
                                              command=self.change_shoot_key)
            self.shoot_key_btn.pack(side="right", padx=20, pady=10)
    
    def create_entry_setting(self, parent, label_text, default_value, callback, row):
        frame = ctk.CTkFrame(parent, corner_radius=10, fg_color="#1a1a1a")
        frame.pack(fill="x", pady=8)
        
        label = ctk.CTkLabel(frame, text=label_text, font=ctk.CTkFont(size=13))
        label.pack(side="left", padx=20, pady=15)
        
        entry = ctk.CTkEntry(frame, width=100, height=35, corner_radius=8,
                            fg_color="#2a2a2a", border_width=0)
        entry.insert(0, str(default_value))
        entry.pack(side="right", padx=20, pady=10)
        
        if "FPS" in label_text:
            self.fps_entry = entry
            entry.bind("<Return>", lambda e: callback())
            entry.bind("<FocusOut>", lambda e: callback())
        else:
            self.tolerance_entry = entry
            entry.bind("<Return>", lambda e: callback())
            entry.bind("<FocusOut>", lambda e: callback())
    
    def create_slider_setting(self, parent, label_text, default_value, callback, row):
        frame = ctk.CTkFrame(parent, corner_radius=10, fg_color="#1a1a1a")
        frame.pack(fill="x", pady=8)
        
        label = ctk.CTkLabel(frame, text=label_text, font=ctk.CTkFont(size=13))
        label.pack(side="left", padx=20, pady=15)
        
        value_label = ctk.CTkLabel(frame, text=f"{default_value:.2f}s",
                                   font=ctk.CTkFont(size=12), text_color="#888888")
        value_label.pack(side="right", padx=20)
        
        slider = ctk.CTkSlider(frame, from_=0, to=2, number_of_steps=100,
                              width=150, height=20, corner_radius=10,
                              button_color="#ff4a4a", button_hover_color="#ef3a3a",
                              progress_color="#df2a2a",
                              command=lambda v: self.slider_callback(v, callback, value_label))
        slider.set(default_value)
        slider.pack(side="right", padx=(0, 10))
        
        if "Reaction" in label_text:
            self.reaction_label = value_label
        else:
            self.delay_label = value_label
    
    def slider_callback(self, value, callback, label):
        label.configure(text=f"{value:.2f}s")
        callback(value)
    
    def create_switch_setting(self, parent, label_text, default_value, callback, row):
        frame = ctk.CTkFrame(parent, corner_radius=10, fg_color="#1a1a1a")
        frame.pack(fill="x", pady=8)
        
        label = ctk.CTkLabel(frame, text=label_text, font=ctk.CTkFont(size=13))
        label.pack(side="left", padx=20, pady=15)
        
        switch = ctk.CTkSwitch(frame, text="", width=50, height=25,
                              corner_radius=12, button_color="#ff4a4a",
                              progress_color="#df2a2a", fg_color="#3a3a3a",
                              command=callback)
        if default_value:
            switch.select()
        switch.pack(side="right", padx=20, pady=10)
        
        self.crosshair_switch = switch
    
    def toggle_shooting(self):
        toggle_shooting()
        self.update_status_display()
        
    def update_status_display(self):
        if settings.shooting_enabled:
            self.status_label.configure(text="ACTIVE", text_color="#44ff44")
        else:
            self.status_label.configure(text="INACTIVE", text_color="#ff4444")
        
        self.root.after(100, self.update_status_display)
    
    def update_fps(self):
        try:
            settings.target_fps = int(self.fps_entry.get())
            settings.save()
        except:
            self.fps_entry.delete(0, "end")
            self.fps_entry.insert(0, str(settings.target_fps))
    
    def update_tolerance(self):
        try:
            settings.tolerance = int(self.tolerance_entry.get())
            settings.save()
        except:
            self.tolerance_entry.delete(0, "end")
            self.tolerance_entry.insert(0, str(settings.tolerance))
    
    def update_reaction_time(self, val):
        settings.reaction_time = float(val)
        settings.save()
    
    def update_delay(self, val):
        settings.delay_between_shots = float(val)
        settings.save()
    
    def change_toggle_key(self):
        self.toggle_key_btn.configure(text="Press key", fg_color="#444444")
        keyboard.unhook_all()
        
        def on_key(e):
            settings.toggle_key = e.name
            self.toggle_key_btn.configure(text=settings.toggle_key.upper(), fg_color="#2a2a2a")
            settings.save()
            keyboard.unhook_all()
            setup_hotkeys()
            return False
        
        keyboard.on_press(on_key, suppress=True)
    
    def change_shoot_key(self):
        self.shoot_key_btn.configure(text="Press key...", fg_color="#444444")
        keyboard.unhook_all()
        
        def on_key(e):
            settings.shoot_key = e.name
            self.shoot_key_btn.configure(text=settings.shoot_key.upper(), fg_color="#2a2a2a")
            settings.save()
            keyboard.unhook_all()
            setup_hotkeys()
            return False
        
        keyboard.on_press(on_key, suppress=True)
    
    def toggle_crosshair(self):
        global crosshair_window
        settings.show_crosshair = self.crosshair_switch.get()
        settings.save()
        
        if crosshair_window:
            if settings.show_crosshair and settings.shooting_enabled:
                crosshair_window.show()
            else:
                crosshair_window.hide()
    
    def on_closing(self):
        settings.running = False
        keyboard.unhook_all()
        if crosshair_window:
            crosshair_window.destroy()
        self.root.destroy()

def setup_hotkeys():
    try:
        keyboard.unhook_all()
        keyboard.add_hotkey(settings.toggle_key, toggle_shooting)
    except:
        pass

# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    setup_hotkeys()
    
    monitor_thread = threading.Thread(target=monitor_screen, daemon=True)
    monitor_thread.start()
    
    root = ctk.CTk()
    crosshair_window = CrosshairOverlay()
    
    app = ShootOnRedGUI(root)
    
    root.mainloop()
