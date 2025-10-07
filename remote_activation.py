import tkinter as tk
from tkinter import messagebox, filedialog, simpledialog, scrolledtext
import threading, time, os, platform, traceback, sys, json, base64, io, tempfile, uuid

# Simplified Windows handling to reduce startup time
if platform.system() == "Windows":
    try:
        import ctypes
        def init_windows_features():
            try:
                from ctypes import wintypes
                ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x00000080)
                try:
                    import win32process
                    win32process.SetProcessWorkingSetSize(-1, -1, -1)
                except: pass
            except: pass
        threading.Thread(target=init_windows_features, daemon=True).start()
    except Exception:
        pass

# Lazy import for optional modules to speed up startup
PY_AUTO = False
HAS_KEYBOARD = False
HAS_PYNPUT = False
HAS_WIN32API = False
pyautogui = None
keyboard = None
pynput = None
mouse = None
pynput_keyboard = None
win32api = None
win32con = None

def init_optional_modules():
    """Initialize optional modules in background thread"""
    global pyautogui, PY_AUTO, keyboard, HAS_KEYBOARD, pynput, HAS_PYNPUT, mouse, pynput_keyboard
    global win32api, win32con, HAS_WIN32API
    try:
        import pyautogui as pg
        pg.FAILSAFE = False
        pyautogui = pg
        PY_AUTO = True
    except: pass

    try:
        import keyboard as kb
        keyboard = kb
        HAS_KEYBOARD = True
    except: pass

    try:
        import pynput as pn
        from pynput import mouse as pm, keyboard as pk
        pynput = pn
        mouse = pm
        pynput_keyboard = pk
        HAS_PYNPUT = True
    except: pass

    try:
        import win32api as w32api
        import win32con as w32con
        win32api = w32api
        win32con = w32con
        HAS_WIN32API = True
    except: pass

threading.Thread(target=init_optional_modules, daemon=True).start()

# Supabase imports
try:
    from supabase import create_client, Client
    HAS_SUPABASE = True
except:
    HAS_SUPABASE = False

# Supabase Configuration
SUPABASE_URL = "https://twnpufintlopmdndvpye.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InR3bnB1ZmludGxvcG1kbmR2cHllIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTk4NDc3NjYsImV4cCI6MjA3NTQyMzc2Nn0.vTop5mq9MpTvqAv-hE_laDoIAZ9s15up6aQqkKJyQxg"

supabase_client: Client = None

def init_supabase():
    """Initialize Supabase client"""
    global supabase_client
    if HAS_SUPABASE and not supabase_client:
        try:
            supabase_client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
            return True
        except Exception as e:
            log_exception(e)
            return False
    return HAS_SUPABASE

def enable_stealth_mode(hwnd):
    """Make window invisible to most detection methods"""
    if platform.system() == "Windows":
        def apply_stealth():
            try:
                import ctypes
                WS_EX_TOOLWINDOW = 0x00000080
                GWL_EXSTYLE = -20
                current_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                new_style = current_style | WS_EX_TOOLWINDOW
                ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)
            except Exception as e:
                log_exception(e)
        threading.Thread(target=apply_stealth, daemon=True).start()

ICON_BASE64 = """AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA============"""
POSITIONS_FILE = "positions.txt"
ERROR_LOG = "error.txt"

VALID_KEYS = {
    "maf1a01":{"label":"1 hour","seconds":60*60},
    "maf1a07":{"label":"7 days","seconds":7*24*3600},
    "maf1a030":{"label":"30 days","seconds":30*24*3600},
    "maf1a090": {"label":"90 days", "seconds":90*24*3600},
    "maf1a0180": {"label":"180 days", "seconds":180*24*3600},
    "maf1a0un":{"label":"lifetime","seconds":None},
}

activation_state = {"activated":False,"expiry":None,"key_used":"","username":"","device_id":"","remote_enabled":False}
APP_REG_KEY = r"Software\M App"
FALLBACK_HIDDEN = os.path.join(os.path.expanduser("~"), ".maf1a_act")

# Remote activation check interval (in seconds)
REMOTE_CHECK_INTERVAL = 30

COLORS = {
    "bg_main": "#000000",
    "bg_secondary": "#3B3B41",
    "bg_accent": "#0C074B",
    "bg_card": "#101020",
    "text_primary": "#ffffff",
    "text_secondary": "#cccccc",
    "text_muted": "#999999",
    "accent_blue": "#860000",
    "accent_green": "#06c025",
    "accent_orange": "#0077FF",
    "accent_red": "#a10909",
    "accent_purple": "#8b5cf6",
    "border": "#404040",
    "hover": "#404040",
    "hover_green": "#00cf80",
    "hover_red": "#e70101",
    "hover_blue": "#500a07",
    "hover_orange": "#018C96",
    "hover_purple": "#7c52e6",
    "transparent": "#1a1a1a",
}

global_mouse_listener = None
global_keyboard_listener = None
tracking_active = False

def get_device_id():
    """Generate unique device ID"""
    try:
        import hashlib
        if platform.system() == "Windows":
            try:
                import subprocess
                result = subprocess.check_output("wmic csproduct get uuid", shell=True).decode()
                uuid_str = result.split('\n')[1].strip()
                return hashlib.sha256(uuid_str.encode()).hexdigest()[:32]
            except:
                pass

        # Fallback to MAC address + hostname
        import getpass
        hostname = platform.node()
        username = getpass.getuser()
        combined = f"{hostname}-{username}"
        return hashlib.sha256(combined.encode()).hexdigest()[:32]
    except:
        return str(uuid.uuid4())[:32]

def sync_activation_to_remote(username, key_used, expiry, activated=True):
    """Sync activation to remote Supabase database"""
    if not init_supabase():
        return False

    try:
        device_id = activation_state.get("device_id", get_device_id())
        activation_state["device_id"] = device_id

        expiry_timestamp = None if expiry is None else time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(expiry))

        data = {
            "username": username,
            "activation_key": key_used,
            "activated": activated,
            "expiry": expiry_timestamp,
            "device_id": device_id,
            "is_blocked": False,
            "last_check": time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())
        }

        # Try to insert or update
        result = supabase_client.table("activations").upsert(data, on_conflict="username,device_id").execute()

        if result.data:
            activation_state["remote_enabled"] = True
            return True
        return False
    except Exception as e:
        log_exception(e)
        return False

def check_remote_activation():
    """Check activation status from remote database"""
    if not init_supabase():
        return None

    try:
        device_id = activation_state.get("device_id", get_device_id())
        username = activation_state.get("username", "")

        if not username:
            return None

        # Query remote activation
        result = supabase_client.table("activations").select("*").eq("username", username).eq("device_id", device_id).maybeSingle().execute()

        if result.data:
            remote_data = result.data

            # Update last_check timestamp
            try:
                supabase_client.table("activations").update({
                    "last_check": time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())
                }).eq("username", username).eq("device_id", device_id).execute()
            except:
                pass

            # Check if blocked
            if remote_data.get("is_blocked", False):
                return {"activated": False, "reason": "blocked"}

            # Check if deactivated remotely
            if not remote_data.get("activated", True):
                return {"activated": False, "reason": "deactivated"}

            # Check expiry
            expiry_str = remote_data.get("expiry")
            if expiry_str:
                import datetime
                expiry_dt = datetime.datetime.strptime(expiry_str, '%Y-%m-%d %H:%M:%S')
                expiry_timestamp = expiry_dt.timestamp()

                if time.time() > expiry_timestamp:
                    return {"activated": False, "reason": "expired", "expiry": expiry_timestamp}

                return {"activated": True, "expiry": expiry_timestamp}

            return {"activated": True, "expiry": None}

        return None
    except Exception as e:
        log_exception(e)
        return None

def create_icon_from_base64():
    """Create icon file from base64 string"""
    def create_async():
        try:
            if not ICON_BASE64.strip() or ICON_BASE64.strip() == "":
                return None
            icon_data = base64.b64decode(ICON_BASE64)
            temp_icon_path = os.path.join(tempfile.gettempdir(), "app_icon.ico")
            with open(temp_icon_path, "wb") as f:
                f.write(icon_data)
            return temp_icon_path
        except Exception as e:
            log_exception(e)
            return None
    return create_async()

def set_window_icon(window):
    """Set window icon using base64 or fallback paths - non-blocking"""
    def set_async():
        try:
            if ICON_BASE64.strip() and ICON_BASE64.strip() != "":
                icon_path = create_icon_from_base64()
                if icon_path and os.path.exists(icon_path):
                    window.after(0, lambda: window.iconbitmap(icon_path))
                    return True

            icon_paths = [
                "app.ico", "assets/app.ico",
                os.path.join(os.path.dirname(sys.argv[0]), "app.ico"),
                os.path.join(os.path.dirname(sys.argv[0]), "assets", "app.ico"),
                os.path.join(os.getcwd(), "app.ico"),
                os.path.join(os.getcwd(), "assets", "app.ico")
            ]

            for icon_path in icon_paths:
                try:
                    if os.path.exists(icon_path):
                        window.after(0, lambda: window.iconbitmap(icon_path))
                        return True
                except Exception:
                    continue
            return False
        except Exception as e:
            log_exception(e)
            return False

    threading.Thread(target=set_async, daemon=True).start()

def minimize_to_tray(app):
    """Minimize application to system tray with stealth mode"""
    def minimize_async():
        try:
            if platform.system() == "Windows":
                hwnd = app.root.winfo_id()
                enable_stealth_mode(hwnd)
                app.root.after(0, lambda: (app.root.withdraw(), app.root.overrideredirect(False), app.root.iconify()))
            else:
                app.root.after(0, lambda: app.root.withdraw())
        except Exception as e:
            log_exception(e)
    threading.Thread(target=minimize_async, daemon=True).start()

def restore_from_tray(app):
    """Restore application from system tray"""
    def restore_async():
        try:
            app.root.after(0, lambda: (
                app.root.deiconify(),
                app.root.lift(),
                app.root.attributes('-topmost', True)
            ))
            app.root.after(100, lambda: app.root.attributes('-topmost', False))
            if platform.system() == "Windows":
                hwnd = app.root.winfo_id()
                enable_stealth_mode(hwnd)
        except Exception as e:
            log_exception(e)
    threading.Thread(target=restore_async, daemon=True).start()

def log_exception(e):
    try:
        print(f"Error: {str(e)}")
    except: pass

def add_hover_effect(button, normal_color, hover_color, transparent=False):
    """Add hover effects to buttons with optional transparency"""
    def on_enter(e):
        if transparent:
            button.config(bg=hover_color, relief="raised", bd=1)
        else:
            button.config(bg=hover_color)

    def on_leave(e):
        if transparent:
            button.config(bg=normal_color, relief="flat", bd=0)
        else:
            button.config(bg=normal_color)

    button.bind("<Enter>", on_enter)
    button.bind("<Leave>", on_leave)

def persist_activation_state():
    def persist_async():
        try:
            payload = base64.b64encode(json.dumps(activation_state).encode()).decode()
            if platform.system()=="Windows":
                try:
                    import winreg
                    key=winreg.CreateKey(winreg.HKEY_CURRENT_USER,APP_REG_KEY)
                    winreg.SetValueEx(key,"act",0,winreg.REG_SZ,payload)
                    winreg.CloseKey(key)
                    return True
                except Exception as e:
                    log_exception(e)
            try:
                with open(FALLBACK_HIDDEN,"w",encoding="utf-8") as f:
                    f.write(payload)
                if platform.system()=="Windows":
                    try:
                        FILE_ATTRIBUTE_HIDDEN = 0x02
                        ctypes.windll.kernel32.SetFileAttributesW(FALLBACK_HIDDEN, FILE_ATTRIBUTE_HIDDEN)
                    except Exception: pass
                return True
            except Exception as e:
                log_exception(e)
                return False
        except Exception as e:
            log_exception(e)
            return False

    threading.Thread(target=persist_async, daemon=True).start()
    return True

def load_persisted_activation_state():
    global activation_state
    try:
        payload = None
        if platform.system()=="Windows":
            try:
                import winreg
                key=winreg.OpenKey(winreg.HKEY_CURRENT_USER,APP_REG_KEY,0,winreg.KEY_READ)
                val,_=winreg.QueryValueEx(key,"act")
                winreg.CloseKey(key)
                payload=val
            except Exception: payload=None
        if not payload and os.path.exists(FALLBACK_HIDDEN):
            try:
                with open(FALLBACK_HIDDEN,"r",encoding="utf-8") as f:
                    payload=f.read().strip()
            except Exception: payload=None
        if payload:
            try:
                data=json.loads(base64.b64decode(payload).decode())
                if isinstance(data,dict):
                    activation_state.update(data)
                    if "username" not in activation_state:
                        activation_state["username"] = ""
                    if "device_id" not in activation_state:
                        activation_state["device_id"] = get_device_id()
                    if "remote_enabled" not in activation_state:
                        activation_state["remote_enabled"] = False
                    return True
            except Exception: pass
    except Exception as e: log_exception(e)
    return False

def clear_persisted_activation_state():
    activation_state.update({"activated":False,"expiry":None,"key_used":"","username":"","device_id":"","remote_enabled":False})
    def clear_async():
        try:
            if platform.system()=="Windows":
                try:
                    import winreg
                    try:
                        key=winreg.OpenKey(winreg.HKEY_CURRENT_USER,APP_REG_KEY,0,winreg.KEY_SET_VALUE)
                        winreg.DeleteValue(key,"act")
                        winreg.CloseKey(key)
                    except Exception: pass
                except Exception: pass
            if os.path.exists(FALLBACK_HIDDEN):
                os.remove(FALLBACK_HIDDEN)
        except Exception as e: log_exception(e)
    threading.Thread(target=clear_async, daemon=True).start()

def is_activated_ok():
    try:
        if not activation_state.get("activated"): return False
        expiry = activation_state.get("expiry")
        if expiry is None: return True
        return time.time() < float(expiry)
    except Exception: return False

def activation_remaining_text():
    if not activation_state.get("activated"): return "Not activated"
    expiry=activation_state.get("expiry")
    if expiry is None: return "Activated (lifetime)"
    remaining=float(expiry)-time.time()
    if remaining<=0: return "EXPIRED"
    h=int(remaining//3600); m=int((remaining%3600)//60); s=int(remaining%60)
    return f"{h:02d}:{m:02d}:{s:02d} remaining"

def get_username_display():
    username = activation_state.get("username", "")
    return username if username else "Unknown User"

def show_custom_message(title, message, msg_type="info", parent=None):
    """Compact message dialog - non-blocking creation"""
    def create_dialog():
        dialog = tk.Toplevel(parent) if parent else tk.Toplevel()
        dialog.title(title)
        dialog.configure(bg=COLORS["bg_main"])
        dialog.geometry("400x180")
        dialog.resizable(False, False)
        dialog.attributes('-alpha', 0.98)
        if parent:
            dialog.transient(parent)
        dialog.grab_set()

        set_window_icon(dialog)

        dialog.update_idletasks()
        w = dialog.winfo_width()
        h = dialog.winfo_height()
        ws = dialog.winfo_screenwidth()
        hs = dialog.winfo_screenheight()
        dialog.geometry(f"+{(ws//2)-(w//2)}+{(hs//2)-(h//2)}")

        icons = {"info": "ℹ️", "success": "✅", "warning": "⚠️", "error": "❌"}
        colors = {"info": COLORS["accent_blue"], "success": COLORS["accent_green"],
                 "warning": COLORS["accent_orange"], "error": COLORS["accent_red"]}

        icon = icons.get(msg_type, "ℹ️")
        color = colors.get(msg_type, COLORS["accent_blue"])

        tk.Label(dialog, text=f"{icon} {title}", fg=color, bg=COLORS["bg_main"],
                font=("Segoe UI", 14, "bold")).pack(pady=15)

        tk.Label(dialog, text=message, fg=COLORS["text_primary"], bg=COLORS["bg_main"],
                font=("Segoe UI", 10), wraplength=350, justify="center").pack(pady=10)

        def on_ok():
            dialog.destroy()

        ok_btn = tk.Button(dialog, text="OK", command=on_ok, bg=color, fg="white",
                          width=12, height=1, font=("Segoe UI", 10, "bold"),
                          relief="flat", bd=0)
        ok_btn.pack(pady=15)

        hover_colors = {"info": COLORS["hover_blue"], "success": COLORS["hover_green"],
                       "warning": COLORS["hover_orange"], "error": COLORS["hover_red"]}
        hover_color = hover_colors.get(msg_type, COLORS["hover_blue"])
        add_hover_effect(ok_btn, color, hover_color)

        dialog.bind('<Return>', lambda e: on_ok())
        dialog.bind('<Escape>', lambda e: on_ok())
        dialog.protocol("WM_DELETE_WINDOW", on_ok)

        dialog.focus_set()
        dialog.wait_window()

    if parent and hasattr(parent, 'after'):
        parent.after(0, create_dialog)
    else:
        create_dialog()

def show_activation_dialog_blocking():
    load_persisted_activation_state()
    if is_activated_ok(): return True
    root=tk.Tk()
    root.withdraw()
    dialog=tk.Toplevel()
    dialog.title("Activation Required")
    dialog.configure(bg=COLORS["bg_main"])
    dialog.geometry("350x400")
    dialog.resizable(False,False)
    dialog.attributes('-alpha', 0.98)

    set_window_icon(dialog)

    try:
        dialog.update_idletasks()
        w=dialog.winfo_width(); h=dialog.winfo_height()
        ws=dialog.winfo_screenwidth(); hs=dialog.winfo_screenheight()
        dialog.geometry(f"+{(ws//2)-(w//2)}+{(hs//2)-(h//2)}")
    except Exception: pass

    tk.Label(dialog, text="🔐 ACTIVATION REQUIRED", fg=COLORS["accent_blue"],
            bg=COLORS["bg_main"], font=("Segoe UI", 16, "bold")).pack(pady=15)

    user_frame = tk.Frame(dialog, bg=COLORS["bg_card"], relief="flat", bd=1)
    user_frame.pack(pady=8, padx=30, fill="x")

    tk.Label(user_frame,text="👤 Enter your name:",fg=COLORS["text_primary"],
            bg=COLORS["bg_card"],font=("Segoe UI",10, "bold")).pack(anchor="w", padx=15, pady=(10,5))
    username_var=tk.StringVar()
    username_entry=tk.Entry(user_frame,textvariable=username_var,
                           bg=COLORS["bg_accent"],fg=COLORS["text_primary"],
                           insertbackground=COLORS["accent_blue"],
                           font=("Segoe UI", 10), relief="flat", bd=0)
    username_entry.pack(fill="x", padx=15, pady=(0,10), ipady=6)

    code_frame = tk.Frame(dialog, bg=COLORS["bg_card"], relief="flat", bd=1)
    code_frame.pack(pady=8, padx=30, fill="x")

    tk.Label(code_frame,text="🔑 Enter activation code:",fg=COLORS["text_primary"],
            bg=COLORS["bg_card"],font=("Segoe UI",10, "bold")).pack(anchor="w", padx=15, pady=(10,5))
    key_var=tk.StringVar()
    entry=tk.Entry(code_frame,textvariable=key_var,show="*",
                  bg=COLORS["bg_accent"],fg=COLORS["text_primary"],
                  insertbackground=COLORS["accent_blue"],
                  font=("Segoe UI", 10), relief="flat", bd=0)
    entry.pack(fill="x", padx=15, pady=(0,10), ipady=6)

    tk.Label(dialog,text="📧 Contact Discord support if you don't have a code",
            fg=COLORS["text_muted"],bg=COLORS["bg_main"],
            font=("Segoe UI", 9)).pack(pady=10)
    result={"ok":False}

    def submit_activation(val, username):
        if not val:
            show_custom_message("Info", "No code entered. Exiting.", "info", dialog)
            dialog.destroy(); root.quit(); sys.exit(0)
        if not username.strip():
            show_custom_message("Warning", "Please enter your name.", "warning", dialog)
            return
        try:
            if val in VALID_KEYS:
                info=VALID_KEYS[val]
                activation_state["activated"]=True
                activation_state["key_used"]=val
                activation_state["username"]=username.strip()
                activation_state["device_id"]=get_device_id()
                activation_state["expiry"]=None if info["seconds"] is None else time.time()+info["seconds"]

                # Sync to remote database
                sync_success = sync_activation_to_remote(
                    username.strip(),
                    val,
                    activation_state["expiry"]
                )

                persist_activation_state()

                status_msg = f"Welcome {username}!\nActivated ({info['label']})"
                if sync_success:
                    status_msg += "\n🌐 Remote control enabled"

                show_custom_message("Activated", status_msg, "success", dialog)
                result["ok"]=True; dialog.destroy(); root.quit(); return
        except Exception: pass
        show_custom_message("Invalid", "Activation code invalid", "error", dialog)

    def on_activate(): submit_activation(key_var.get().strip(), username_var.get().strip())
    def on_cancel():
        show_custom_message("Info", "Program not activated. Exiting.", "info", dialog)
        dialog.destroy(); root.quit(); sys.exit(0)

    btnf=tk.Frame(dialog,bg=COLORS["bg_main"]); btnf.pack(pady=20)

    activate_btn = tk.Button(btnf,text="✓ Activate",command=on_activate,
                            bg=COLORS["accent_green"],fg="white",width=12, height=2,
                            font=("Segoe UI",10,"bold"), relief="flat", bd=0)
    activate_btn.pack(side="left",padx=10)
    add_hover_effect(activate_btn, COLORS["accent_green"], COLORS["hover_green"])

    cancel_btn = tk.Button(btnf,text="✗ Cancel",command=on_cancel,
                          bg=COLORS["accent_red"],fg="white",width=12, height=2,
                          font=("Segoe UI",10,"bold"), relief="flat", bd=0)
    cancel_btn.pack(side="left",padx=10)
    add_hover_effect(cancel_btn, COLORS["accent_red"], COLORS["hover_red"])

    username_entry.focus_set()
    dialog.protocol("WM_DELETE_WINDOW",on_cancel)

    def on_username_enter(event):
        entry.focus_set()
    def on_code_enter(event):
        on_activate()

    username_entry.bind('<Return>', on_username_enter)
    entry.bind('<Return>', on_code_enter)

    root.mainloop()
    return result.get("ok",False)

def play_beep():
    def beep_async():
        try:
            if platform.system()=="Windows":
                import winsound; winsound.MessageBeep()
            else: print('\a')
        except Exception: pass
    threading.Thread(target=beep_async, daemon=True).start()

class GlobalHotkeys:
    def __init__(self, app):
        self.app = app
        self.hotkeys_set = False
        self.global_listener = None

    def start(self):
        def start_async():
            max_wait = 50
            wait_count = 0
            while not (HAS_PYNPUT or HAS_KEYBOARD) and wait_count < max_wait:
                time.sleep(0.1)
                wait_count += 1

            if not HAS_PYNPUT:
                if HAS_KEYBOARD and keyboard:
                    try:
                        keyboard.add_hotkey('f2', lambda: self.app.root.after(0, self.app.on_start), suppress=False)
                        keyboard.add_hotkey('f3', lambda: self.app.root.after(0, self.app.on_stop), suppress=False)
                        keyboard.add_hotkey('f4', lambda: self.app.root.after(0, self.app.toggle_unified_recording), suppress=False)
                        keyboard.add_hotkey('f5', lambda: self.app.root.after(0, self.app.on_exit), suppress=False)
                        keyboard.add_hotkey('f1', lambda: self.app.root.after(0, self.app.show_hide_window), suppress=False)
                        self.hotkeys_set = True
                    except Exception as e:
                        log_exception(e)
                return

            if HAS_PYNPUT and pynput_keyboard:
                try:
                    def on_key_press(key):
                        try:
                            if hasattr(key, 'name'):
                                key_name = key.name
                            else:
                                key_name = str(key).replace("'", "")

                            if key_name == 'f2':
                                self.app.root.after(0, self.app.on_start)
                            elif key_name == 'f3':
                                self.app.root.after(0, self.app.on_stop)
                            elif key_name == 'f4':
                                self.app.root.after(0, self.app.toggle_unified_recording)
                            elif key_name == 'f5':
                                self.app.root.after(0, self.app.on_exit)
                            elif key_name == 'f1':
                                self.app.root.after(0, self.app.show_hide_window)
                        except Exception as e:
                            log_exception(e)

                    self.global_listener = pynput_keyboard.Listener(on_press=on_key_press, suppress=False)
                    self.global_listener.start()
                    self.hotkeys_set = True
                except Exception as e:
                    log_exception(e)

        threading.Thread(target=start_async, daemon=True).start()

    def stop(self):
        if self.global_listener:
            try:
                self.global_listener.stop()
            except Exception:
                pass

        if self.hotkeys_set and HAS_KEYBOARD and keyboard:
            try:
                keyboard.unhook_all_hotkeys()
            except Exception:
                pass

        self.hotkeys_set = False

class AutoClicker:
    def __init__(self):
        self.positions = []
        self.click_delay = 0.001
        self.running = False
        self.thread = None
        self.hold_e = False
        self.keyboard_delay = 0.001
        self.press_enter_enabled = False
        self.press_f_enabled = False
        self.press_q_enabled = False
        self.press_e_every_minute = False
        self.right_click_every_half_second = False
        self.last_enter_time = time.time()
        self.last_f_time = time.time()
        self.last_q_time = time.time()
        self.last_e_minute_time = time.time()
        self.last_right_click_time = time.time()
        self.keyboard_actions = []
        self.mouse_movements = []
        self.stop_event = threading.Event()
        self.playback_speed = 1.0

    def add_position(self, x, y, btn="left"):
        self.positions.append((x, y, btn))
        self.save_positions_txt()
        return True

    def add_keyboard_action(self, action_type, value, repeat_count=1):
        self.keyboard_actions.append((action_type, value, int(repeat_count)))
        self.save_positions_txt()
        return True

    def add_mouse_movement(self, dx, dy, duration=0.0, move_type="relative"):
        self.mouse_movements.append((dx, dy, duration, move_type))
        self.save_positions_txt()
        return True

    def remove_position(self, index):
        if 0 <= index < len(self.positions):
            self.positions.pop(index)
            self.save_positions_txt()
            return True
        return False

    def clear_positions(self):
        self.positions = []
        self.keyboard_actions = []
        self.mouse_movements = []
        self.save_positions_txt()
        return True

    def save_positions_txt(self, path=None):
        try:
            file_path = path or POSITIONS_FILE
            with open(file_path, "w", encoding="utf-8") as f:
                for x, y, btn in self.positions:
                    f.write(f"{x},{y},{btn}\n")
                for action_type, value, repeat_count in self.keyboard_actions:
                    f.write(f"KEYBOARD,{action_type},{value},{repeat_count}\n")
                for dx, dy, duration, move_type in self.mouse_movements:
                    f.write(f"MOUSE_MOVE,{dx},{dy},{duration},{move_type}\n")
            return True
        except Exception as e:
            log_exception(e)
            return False

    def load_positions_txt(self, path=None):
        try:
            file_path = path or POSITIONS_FILE
            if not os.path.exists(file_path):
                return True
            self.positions = []
            self.keyboard_actions = []
            self.mouse_movements = []
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("KEYBOARD,"):
                        parts = line.split(",", 3)
                        if len(parts) >= 3:
                            action_type = parts[1]
                            value = parts[2]
                            repeat_count = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 1
                            self.keyboard_actions.append((action_type, value, repeat_count))
                    elif line.startswith("MOUSE_MOVE,"):
                        parts = line.split(",")
                        if len(parts) >= 3:
                            dx = int(parts[1])
                            dy = int(parts[2])
                            duration = float(parts[3]) if len(parts) > 3 else 0.0
                            move_type = parts[4] if len(parts) > 4 else "relative"
                            self.mouse_movements.append((dx, dy, duration, move_type))
                    elif line.startswith("KEY,"):
                        self.keyboard_actions.append(("key", line.split(",", 1)[1], 1))
                    else:
                        parts = line.split(",")
                        if len(parts) >= 2:
                            x = int(parts[0].strip())
                            y = int(parts[1].strip())
                            btn = parts[2].strip() if len(parts) > 2 else "left"
                            self.positions.append((x, y, btn))
            return True
        except Exception as e:
            log_exception(e)
            return False

    def _run_loop(self):
        try:
            max_wait = 50
            wait_count = 0
            while not (PY_AUTO or HAS_KEYBOARD or HAS_WIN32API) and wait_count < max_wait:
                time.sleep(0.1)
                wait_count += 1

            while self.running and not self.stop_event.is_set():
                current_time = time.time()

                if self.press_enter_enabled and (current_time - self.last_enter_time) >= 10:
                    if HAS_KEYBOARD and keyboard:
                        try:
                            keyboard.press_and_release('enter')
                        except Exception:
                            pass
                    elif PY_AUTO and pyautogui:
                        try:
                            pyautogui.press('enter')
                        except Exception:
                            pass
                    self.last_enter_time = current_time

                if self.press_f_enabled and (current_time - self.last_f_time) >= 5:
                    if HAS_KEYBOARD and keyboard:
                        try:
                            keyboard.press_and_release('f')
                        except Exception:
                            pass
                    elif PY_AUTO and pyautogui:
                        try:
                            pyautogui.press('f')
                        except Exception:
                            pass
                    self.last_f_time = current_time

                if self.press_q_enabled and (current_time - self.last_q_time) >= 2:
                    if HAS_KEYBOARD and keyboard:
                        try:
                            keyboard.press_and_release('q')
                        except Exception:
                            pass
                    elif PY_AUTO and pyautogui:
                        try:
                            pyautogui.press('q')
                        except Exception:
                            pass
                    self.last_q_time = current_time

                if self.press_e_every_minute and (current_time - self.last_e_minute_time) >= 60:
                    if HAS_KEYBOARD and keyboard:
                        try:
                            keyboard.press_and_release('e')
                        except Exception:
                            pass
                    elif PY_AUTO and pyautogui:
                        try:
                            pyautogui.press('e')
                        except Exception:
                            pass
                    self.last_e_minute_time = current_time

                if self.right_click_every_half_second and (current_time - self.last_right_click_time) >= 3.0:
                    if HAS_WIN32API and win32api and win32con:
                        try:
                            x, y = win32api.GetCursorPos()
                            win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
                            time.sleep(0.01)
                            win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)
                        except Exception:
                            pass
                    elif PY_AUTO and pyautogui:
                        try:
                            pyautogui.click(button='right')
                        except Exception:
                            pass
                    self.last_right_click_time = current_time

                if self.positions or self.keyboard_actions or self.mouse_movements:
                    if self.hold_e:
                        if HAS_KEYBOARD and keyboard:
                            try:
                                keyboard.press_and_release('e')
                            except Exception:
                                pass
                        elif PY_AUTO and pyautogui:
                            try:
                                pyautogui.press('e')
                            except Exception:
                                pass
                        time.sleep(0.1)

                    all_actions = []
                    for dx, dy, duration, move_type in self.mouse_movements:
                        all_actions.append(('move', dx, dy, duration, move_type))
                    for x, y, btn in self.positions:
                        all_actions.append(('click', x, y, btn, None))
                    for action_type, value, repeat_count in self.keyboard_actions:
                        all_actions.append(('keyboard', action_type, value, repeat_count, None))

                    for action in all_actions:
                        if not self.running or self.stop_event.is_set():
                            break

                        if action[0] == 'move':
                            _, dx, dy, duration, move_type = action
                            scaled_duration = duration / self.playback_speed

                            if move_type == "relative":
                                if HAS_WIN32API and win32api and win32con:
                                    try:
                                        win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, int(dx), int(dy), 0, 0)
                                        time.sleep(max(0.001, scaled_duration))
                                    except Exception:
                                        pass
                                elif PY_AUTO and pyautogui:
                                    try:
                                        current_x, current_y = pyautogui.position()
                                        if scaled_duration > 0:
                                            pyautogui.moveTo(current_x + int(dx), current_y + int(dy), duration=scaled_duration)
                                        else:
                                            pyautogui.moveTo(current_x + int(dx), current_y + int(dy))
                                    except Exception:
                                        pass
                            else:
                                if PY_AUTO and pyautogui:
                                    try:
                                        if scaled_duration > 0:
                                            pyautogui.moveTo(int(dx), int(dy), duration=scaled_duration)
                                        else:
                                            pyautogui.moveTo(int(dx), int(dy))
                                    except Exception:
                                        pass
                                elif HAS_WIN32API and win32api:
                                    try:
                                        win32api.SetCursorPos((int(dx), int(dy)))
                                        time.sleep(max(0.001, scaled_duration))
                                    except Exception:
                                        pass

                        elif action[0] == 'click':
                            _, x, y, btn, _ = action
                            if HAS_WIN32API and win32api and win32con:
                                try:
                                    win32api.SetCursorPos((int(x), int(y)))
                                    time.sleep(0.01)
                                    if btn == 'left':
                                        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                                        time.sleep(0.02)
                                        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                                    else:
                                        win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
                                        time.sleep(0.02)
                                        win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)
                                except Exception:
                                    pass
                            elif PY_AUTO and pyautogui:
                                try:
                                    pyautogui.click(x=int(x), y=int(y), button=btn)
                                except Exception:
                                    pass
                            time.sleep(max(0.001, float(self.click_delay) / self.playback_speed))

                        elif action[0] == 'keyboard':
                            _, action_type, value, repeat_count, _ = action

                            if HAS_KEYBOARD and keyboard:
                                try:
                                    for _ in range(repeat_count):
                                        if not self.running or self.stop_event.is_set():
                                            break
                                        if action_type == "type":
                                            keyboard.write(value, delay=0)
                                        elif action_type == "press_release":
                                            key_name, duration = value.split(":")
                                            keyboard.press(key_name)
                                            time.sleep(float(duration) / self.playback_speed)
                                            keyboard.release(key_name)
                                        else:
                                            keyboard.press_and_release(value)
                                        time.sleep(max(0.001, float(self.keyboard_delay) / self.playback_speed))
                                except Exception:
                                    pass
                            elif PY_AUTO and pyautogui:
                                try:
                                    for _ in range(repeat_count):
                                        if not self.running or self.stop_event.is_set():
                                            break
                                        if action_type == "type":
                                            pyautogui.typewrite(value, interval=0)
                                        else:
                                            pyautogui.press(value)
                                        time.sleep(max(0.001, float(self.keyboard_delay) / self.playback_speed))
                                except Exception:
                                    pass
                else:
                    time.sleep(0.001)
        except Exception as e:
            log_exception(e)

    def start(self):
        if self.running:
            return
        self.stop_event.clear()
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        play_beep()

    def stop(self):
        if not self.running:
            return
        self.running = False
        self.stop_event.set()
        try:
            if self.thread and self.thread.is_alive():
                self.thread.join(timeout=0.5)
        except Exception:
            pass
        play_beep()

class GlobalMouseTracker:
    def __init__(self, app):
        self.app = app
        self.mouse_listener = None
        self.tracking = False

    def start_tracking(self):
        if self.tracking:
            return

        self.tracking = True

        def start_async():
            max_wait = 50
            wait_count = 0
            while not (HAS_PYNPUT or PY_AUTO) and wait_count < max_wait:
                time.sleep(0.1)
                wait_count += 1

            if HAS_PYNPUT and mouse:
                def on_click(x, y, button, pressed):
                    if pressed and self.tracking:
                        try:
                            self.app.root.after(0, lambda: self.app.add_global_position_silent(x, y))
                        except Exception as e:
                            log_exception(e)
                        return False

                try:
                    self.mouse_listener = mouse.Listener(on_click=on_click)
                    self.mouse_listener.start()
                    return True
                except Exception as e:
                    log_exception(e)
                    return False

            elif PY_AUTO and pyautogui:
                def monitor_mouse():
                    start_time = time.time()
                    try:
                        last_x, last_y = pyautogui.position()
                    except:
                        return False

                    while self.tracking and (time.time() - start_time) < 30:
                        try:
                            current_x, current_y = pyautogui.position()
                            if (current_x != last_x or current_y != last_y):
                                last_x, last_y = current_x, current_y

                            if platform.system() == "Windows":
                                try:
                                    import ctypes
                                    if ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000:
                                        if self.tracking:
                                            self.app.root.after(0, lambda: self.app.add_global_position_silent(current_x, current_y))
                                            break
                                except Exception:
                                    pass

                            time.sleep(0.01)
                        except Exception:
                            break

                    self.tracking = False

                threading.Thread(target=monitor_mouse, daemon=True).start()
                return True

            return False

        threading.Thread(target=start_async, daemon=True).start()
        return True

    def stop_tracking(self):
        if not self.tracking:
            return

        self.tracking = False

        if self.mouse_listener:
            try:
                self.mouse_listener.stop()
            except Exception:
                pass

class UnifiedRecorder:
    def __init__(self, app):
        self.app = app
        self.recording = False
        self.recorded_events = []
        self.monitor_thread = None
        self.pressed_keys = {}
        self.keyboard_hook = None
        self.mouse_listener = None
        self.start_time = None
        self.last_left_click = 0
        self.last_right_click = 0
        self.click_debounce = 0.05
        self.ignore_keys = {'f1', 'f2', 'f3', 'f4', 'f5'}
        self.last_mouse_pos = None

    def start_recording(self):
        if self.recording:
            return

        self.recording = True
        self.recorded_events = []
        self.pressed_keys = {}
        self.start_time = time.time()
        self.last_left_click = 0
        self.last_right_click = 0
        self.last_mouse_pos = None

        if HAS_WIN32API and win32api:
            try:
                self.last_mouse_pos = win32api.GetCursorPos()
            except:
                pass
        elif PY_AUTO and pyautogui:
            try:
                self.last_mouse_pos = pyautogui.position()
            except:
                pass

        def start_async():
            max_wait = 20
            wait_count = 0
            while not (HAS_KEYBOARD or HAS_WIN32API) and wait_count < max_wait:
                time.sleep(0.05)
                wait_count += 1

            if HAS_KEYBOARD and keyboard:
                def on_key_event(event):
                    if not self.recording:
                        return

                    try:
                        key_name = event.name if hasattr(event, 'name') else str(event)

                        if key_name.lower() in self.ignore_keys:
                            return

                        current_time = time.time() - self.start_time

                        if event.event_type == 'down':
                            if key_name not in self.pressed_keys:
                                self.pressed_keys[key_name] = current_time

                        elif event.event_type == 'up':
                            if key_name in self.pressed_keys:
                                press_time = self.pressed_keys[key_name]
                                duration = current_time - press_time

                                self.recorded_events.append({
                                    'type': 'keyboard',
                                    'action': 'press_release',
                                    'key': key_name,
                                    'duration': round(duration, 3),
                                    'timestamp': press_time
                                })

                                del self.pressed_keys[key_name]
                                self.app.root.after(0, lambda: self.app.update_unified_display())

                    except Exception as e:
                        log_exception(e)

                try:
                    keyboard.hook(on_key_event)
                    self.keyboard_hook = True
                except Exception as e:
                    log_exception(e)

            if HAS_WIN32API and win32api and win32con:
                def monitor_mouse():
                    try:
                        last_pos = win32api.GetCursorPos()
                        last_move_time = time.time()
                        last_left = False
                        last_right = False

                        while self.recording:
                            try:
                                current_time = time.time()
                                current_pos = win32api.GetCursorPos()

                                if abs(current_pos[0] - last_pos[0]) > 3 or abs(current_pos[1] - last_pos[1]) > 3:
                                    dx = current_pos[0] - last_pos[0]
                                    dy = current_pos[1] - last_pos[1]
                                    duration = current_time - last_move_time

                                    self.recorded_events.append({
                                        'type': 'mouse_move',
                                        'dx': dx,
                                        'dy': dy,
                                        'duration': round(duration, 3),
                                        'timestamp': current_time - self.start_time,
                                        'move_type': 'relative'
                                    })

                                    last_pos = current_pos
                                    last_move_time = current_time
                                    self.app.root.after(0, lambda: self.app.update_unified_display())

                                try:
                                    import ctypes
                                    left_state = bool(ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000)
                                    right_state = bool(ctypes.windll.user32.GetAsyncKeyState(0x02) & 0x8000)

                                    if left_state and not last_left:
                                        if current_time - self.last_left_click >= self.click_debounce:
                                            self.recorded_events.append({
                                                'type': 'mouse_click',
                                                'x': current_pos[0],
                                                'y': current_pos[1],
                                                'button': 'left',
                                                'timestamp': current_time - self.start_time
                                            })
                                            self.last_left_click = current_time
                                            self.app.root.after(0, lambda: self.app.update_unified_display())

                                    if right_state and not last_right:
                                        if current_time - self.last_right_click >= self.click_debounce:
                                            self.recorded_events.append({
                                                'type': 'mouse_click',
                                                'x': current_pos[0],
                                                'y': current_pos[1],
                                                'button': 'right',
                                                'timestamp': current_time - self.start_time
                                            })
                                            self.last_right_click = current_time
                                            self.app.root.after(0, lambda: self.app.update_unified_display())

                                    last_left = left_state
                                    last_right = right_state
                                except Exception:
                                    pass

                                time.sleep(0.005)
                            except Exception as e:
                                log_exception(e)
                                break
                    except Exception as e:
                        log_exception(e)

                self.monitor_thread = threading.Thread(target=monitor_mouse, daemon=True)
                self.monitor_thread.start()

        threading.Thread(target=start_async, daemon=True).start()
        return True

    def stop_recording(self):
        if not self.recording:
            return

        self.recording = False

        for key_name in list(self.pressed_keys.keys()):
            press_time = self.pressed_keys[key_name]
            duration = time.time() - self.start_time - press_time
            self.recorded_events.append({
                'type': 'keyboard',
                'action': 'press_release',
                'key': key_name,
                'duration': round(duration, 3),
                'timestamp': press_time
            })
        self.pressed_keys = {}

        if HAS_KEYBOARD and keyboard and self.keyboard_hook:
            try:
                keyboard.unhook_all()
                self.keyboard_hook = False
            except Exception:
                pass

        if self.mouse_listener:
            try:
                self.mouse_listener.stop()
            except Exception:
                pass

        if self.monitor_thread and self.monitor_thread.is_alive():
            try:
                self.monitor_thread.join(timeout=0.5)
            except Exception:
                pass

    def get_recorded_events(self):
        return sorted(self.recorded_events, key=lambda x: x['timestamp'])

    def clear_recorded_events(self):
        self.recorded_events = []
        self.pressed_keys = {}

class RemoteActivationMonitor:
    """Monitor remote activation status periodically"""
    def __init__(self, app):
        self.app = app
        self.running = False
        self.monitor_thread = None

    def start(self):
        if self.running:
            return

        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()

    def stop(self):
        self.running = False
        if self.monitor_thread:
            try:
                self.monitor_thread.join(timeout=1.0)
            except:
                pass

    def _monitor_loop(self):
        """Periodically check remote activation status"""
        while self.running:
            try:
                time.sleep(REMOTE_CHECK_INTERVAL)

                if not self.running:
                    break

                # Check if remote monitoring is enabled
                if not activation_state.get("remote_enabled", False):
                    continue

                # Check remote activation status
                remote_status = check_remote_activation()

                if remote_status is None:
                    continue

                # Handle remote status
                if not remote_status.get("activated", True):
                    reason = remote_status.get("reason", "unknown")

                    # Update local state
                    activation_state["activated"] = False
                    persist_activation_state()

                    # Stop clicker if running
                    if self.app.clicker.running:
                        self.app.root.after(0, self.app.on_stop)

                    # Show message based on reason
                    if reason == "blocked":
                        self.app.root.after(0, lambda: show_custom_message(
                            "Blocked",
                            "Your activation has been blocked by administrator",
                            "error",
                            self.app.root
                        ))
                    elif reason == "deactivated":
                        self.app.root.after(0, lambda: show_custom_message(
                            "Deactivated",
                            "Your activation has been deactivated remotely",
                            "error",
                            self.app.root
                        ))
                    elif reason == "expired":
                        self.app.root.after(0, lambda: show_custom_message(
                            "Expired",
                            "Your activation has expired",
                            "error",
                            self.app.root
                        ))

                    self.app.activation_expired = True

                else:
                    # Update expiry if changed remotely
                    remote_expiry = remote_status.get("expiry")
                    if remote_expiry != activation_state.get("expiry"):
                        activation_state["expiry"] = remote_expiry
                        persist_activation_state()

            except Exception as e:
                log_exception(e)

class MaF1aApp:
    def __init__(self, root):
        self.root = root
        self.root.title("M Pro")
        self.root.geometry("380x760")
        self.root.resizable(False, False)
        self.root.configure(bg=COLORS["bg_main"])

        self.root.attributes('-alpha', 0.96)

        if platform.system() == "Windows":
            self.root.after(500, self._apply_stealth_mode)

        set_window_icon(self.root)

        self.clicker = AutoClicker()
        self.hotkeys = GlobalHotkeys(self)
        self.mouse_tracker = GlobalMouseTracker(self)
        self.unified_recorder = UnifiedRecorder(self)
        self.remote_monitor = RemoteActivationMonitor(self)
        self.tracking_mouse = False
        self.activation_expired = False
        self.hidden = False

        self._build_ui()
        threading.Thread(target=self._load_positions_async, daemon=True).start()
        threading.Thread(target=self.hotkeys.start, daemon=True).start()

        # Start remote monitoring if enabled
        if activation_state.get("remote_enabled", False):
            self.remote_monitor.start()

        self.root.after(1000, self._update_status_label)

    def _load_positions_async(self):
        self.clicker.load_positions_txt()
        self.root.after(0, self.refresh_positions)

    def _apply_stealth_mode(self):
        def apply_async():
            try:
                hwnd = self.root.winfo_id()
                enable_stealth_mode(hwnd)
            except Exception as e:
                log_exception(e)
        threading.Thread(target=apply_async, daemon=True).start()

    def show_hide_window(self):
        try:
            if self.hidden:
                restore_from_tray(self)
                self.hidden = False
            else:
                minimize_to_tray(self)
                self.hidden = True
        except Exception as e:
            log_exception(e)

    def _build_ui(self):
        main = tk.Frame(self.root, bg=COLORS["bg_main"])
        main.pack(fill="both", expand=True, padx=8, pady=8)

        header_frame = tk.Frame(main, bg=COLORS["bg_main"])
        header_frame.pack(fill="x", pady=(0,6))

        user_info_frame = tk.Frame(header_frame, bg=COLORS["bg_card"], relief="flat", bd=1)
        user_info_frame.pack(side="left", anchor="w", padx=(0,8))

        tk.Label(user_info_frame, text="User", fg=COLORS["accent_blue"],
                bg=COLORS["bg_card"], font=("Segoe UI", 8, "bold")).pack(padx=8, pady=(5,2))

        self.username_label = tk.Label(user_info_frame, text=f"👤 {get_username_display()}",
                                   fg=COLORS["text_primary"], bg=COLORS["bg_card"],
                                   font=("Segoe UI", 8))
        self.username_label.pack(anchor="w", padx=8)

        self.activation_status = tk.Label(user_info_frame, text=f"⏰ {activation_remaining_text()}",
                                      fg=COLORS["accent_green"], bg=COLORS["bg_card"],
                                      font=("Segoe UI", 8))
        self.activation_status.pack(anchor="w", padx=8, pady=(0,5))

        logo_frame = tk.Frame(header_frame, bg=COLORS["bg_main"])
        logo_frame.pack(side="left", expand=True)

        title = tk.Label(logo_frame, text="Ⓜ", fg=COLORS["accent_purple"],
                      bg=COLORS["bg_main"], font=("Segoe UI", 18, "bold"))
        title.pack()

        subtitle = tk.Label(logo_frame, text="M ", fg=COLORS["text_secondary"],
                         bg=COLORS["bg_main"], font=("Segoe UI", 7))
        subtitle.pack()

        right_frame = tk.Frame(header_frame, bg=COLORS["bg_main"])
        right_frame.pack(side="right", anchor="e")

        hide_btn = tk.Button(right_frame, text="🔽 (F1)", command=self.show_hide_window,
                            bg=COLORS["transparent"], fg="white", width=9, height=1,
                            font=("Segoe UI", 7, "bold"), relief="flat", bd=0)
        hide_btn.pack(pady=(0,3))
        add_hover_effect(hide_btn, COLORS["transparent"], COLORS["hover"], transparent=True)

        reset_btn = tk.Button(right_frame, text="🔄Reset", command=self.clear_activation,
                             bg=COLORS["accent_red"], fg="white", width=9, height=1,
                             font=("Segoe UI", 7, "bold"), relief="flat", bd=0)
        reset_btn.pack()
        add_hover_effect(reset_btn, COLORS["accent_red"], COLORS["hover_red"])

        config_section = tk.Frame(main, bg=COLORS["bg_card"], relief="flat", bd=1)
        config_section.pack(fill="x", pady=(0,5))

        tk.Label(config_section, text="⚙️ Config", fg=COLORS["accent_blue"],
                bg=COLORS["bg_card"], font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=10, pady=(5,3))

        options_grid = tk.Frame(config_section, bg=COLORS["bg_card"])
        options_grid.pack(fill="x", padx=10, pady=(0,5))

        self.chk_hold_e_var = tk.BooleanVar(value=False)
        self.chk_enter_var = tk.BooleanVar()
        self.chk_f_var = tk.BooleanVar()
        self.chk_q_var = tk.BooleanVar()
        self.chk_e_minute_var = tk.BooleanVar()
        self.chk_right_click_half_second_var = tk.BooleanVar()

        chk1 = tk.Checkbutton(options_grid, text="🅴E before actions",
                             variable=self.chk_hold_e_var, fg=COLORS["text_primary"],
                             bg=COLORS["bg_card"], selectcolor=COLORS["bg_accent"],
                             font=("Segoe UI", 8))
        chk1.grid(row=0, column=0, sticky="w", padx=(0,10), pady=2)

        chk2 = tk.Checkbutton(options_grid, text="↵ Enter/10s",
                             variable=self.chk_enter_var, fg=COLORS["text_primary"],
                             bg=COLORS["bg_card"], selectcolor=COLORS["bg_accent"],
                             font=("Segoe UI", 8))
        chk2.grid(row=0, column=1, sticky="w", pady=2)

        chk3 = tk.Checkbutton(options_grid, text="🅵 F/5s",
                             variable=self.chk_f_var, fg=COLORS["text_primary"],
                             bg=COLORS["bg_card"], selectcolor=COLORS["bg_accent"],
                             font=("Segoe UI", 8))
        chk3.grid(row=1, column=0, sticky="w", padx=(0,10), pady=2)

        chk4 = tk.Checkbutton(options_grid, text="🅠 Q/2s",
                             variable=self.chk_q_var, fg=COLORS["text_primary"],
                             bg=COLORS["bg_card"], selectcolor=COLORS["bg_accent"],
                             font=("Segoe UI", 8))
        chk4.grid(row=1, column=1, sticky="w", pady=2)

        chk5 = tk.Checkbutton(options_grid, text="🅴 E/1min",
                             variable=self.chk_e_minute_var, fg=COLORS["text_primary"],
                             bg=COLORS["bg_card"], selectcolor=COLORS["bg_accent"],
                             font=("Segoe UI", 8))
        chk5.grid(row=2, column=0, sticky="w", padx=(0,10), pady=2)

        chk6 = tk.Checkbutton(options_grid, text="RightClick/3.0s",
                             variable=self.chk_right_click_half_second_var, fg=COLORS["text_primary"],
                             bg=COLORS["bg_card"], selectcolor=COLORS["bg_accent"],
                             font=("Segoe UI", 8))
        chk6.grid(row=2, column=1, sticky="w", pady=2)

        delay_frame = tk.Frame(options_grid, bg=COLORS["bg_card"])
        delay_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(3,0))

        tk.Label(delay_frame, text="⚡ Click Delay:", fg=COLORS["text_primary"],
                bg=COLORS["bg_card"], font=("Segoe UI", 8)).grid(row=0, column=0, sticky="w", padx=(0,3))
        self.delay_entry = tk.Entry(delay_frame, width=5, bg=COLORS["bg_accent"],
                                 fg=COLORS["text_primary"], font=("Segoe UI", 8),
                                 relief="flat", bd=0, insertbackground=COLORS["accent_blue"])
        self.delay_entry.insert(0, "0.001")
        self.delay_entry.grid(row=0, column=1, padx=(0,15), ipady=2)

        tk.Label(delay_frame, text="⌨️ KB Delay:", fg=COLORS["text_primary"],
                bg=COLORS["bg_card"], font=("Segoe UI", 8)).grid(row=0, column=2, sticky="w", padx=(0,3))
        self.kb_delay_entry = tk.Entry(delay_frame, width=5, bg=COLORS["bg_accent"],
                                   fg=COLORS["text_primary"], font=("Segoe UI", 8),
                                   relief="flat", bd=0, insertbackground=COLORS["accent_blue"])
        self.kb_delay_entry.insert(0, "0.001")
        self.kb_delay_entry.grid(row=0, column=3, ipady=2)

        speed_frame = tk.Frame(config_section, bg=COLORS["bg_card"])
        speed_frame.pack(fill="x", padx=10, pady=(5,5))

        tk.Label(speed_frame, text="🎚️ Playback Speed:", fg=COLORS["text_primary"],
                bg=COLORS["bg_card"], font=("Segoe UI", 8, "bold")).pack(side="left", padx=(0,5))

        self.speed_var = tk.DoubleVar(value=1.0)
        self.speed_scale = tk.Scale(speed_frame, from_=0.1, to=5.0, resolution=0.1,
                                    orient=tk.HORIZONTAL, variable=self.speed_var,
                                    bg=COLORS["bg_accent"], fg=COLORS["text_primary"],
                                    highlightthickness=0, troughcolor=COLORS["bg_main"],
                                    font=("Segoe UI", 7), length=180, command=self.update_speed_label)
        self.speed_scale.pack(side="left", padx=(0,5))

        self.speed_label = tk.Label(speed_frame, text="1.0x", fg=COLORS["accent_green"],
                                    bg=COLORS["bg_card"], font=("Segoe UI", 8, "bold"))
        self.speed_label.pack(side="left")

        add_section = tk.Frame(main, bg=COLORS["bg_card"], relief="flat", bd=1)
        add_section.pack(fill="x", pady=(0,5))

        tk.Label(add_section, text="Add Actions", fg=COLORS["accent_orange"],
                bg=COLORS["bg_card"], font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=10, pady=(5,3))

        main_container = tk.Frame(add_section, bg=COLORS["bg_card"])
        main_container.pack(fill="x", padx=10, pady=(0,5))

        left_side = tk.Frame(main_container, bg=COLORS["bg_card"])
        left_side.pack(side="left", fill="both", expand=True, padx=(0,5))

        pos_row = tk.Frame(left_side, bg=COLORS["bg_card"])
        pos_row.pack(fill="x", pady=(0,3))

        tk.Label(pos_row, text="Position:", fg=COLORS["text_secondary"],
                bg=COLORS["bg_card"], font=("Segoe UI", 8)).pack(side="left")

        tk.Label(pos_row, text="X:", fg=COLORS["text_primary"],
                bg=COLORS["bg_card"], font=("Segoe UI", 8)).pack(side="left", padx=(10,2))
        self.x_entry = tk.Entry(pos_row, width=5, bg=COLORS["bg_accent"],
                            fg=COLORS["text_primary"], font=("Segoe UI", 8),
                            relief="flat", bd=0, insertbackground=COLORS["accent_blue"])
        self.x_entry.pack(side="left", padx=(0,8), ipady=2)

        tk.Label(pos_row, text="Y:", fg=COLORS["text_primary"],
                bg=COLORS["bg_card"], font=("Segoe UI", 8)).pack(side="left", padx=(0,2))
        self.y_entry = tk.Entry(pos_row, width=5, bg=COLORS["bg_accent"],
                            fg=COLORS["text_primary"], font=("Segoe UI", 8),
                            relief="flat", bd=0, insertbackground=COLORS["accent_blue"])
        self.y_entry.pack(side="left", ipady=2)

        btn_row1 = tk.Frame(left_side, bg=COLORS["bg_card"])
        btn_row1.pack(fill="x", pady=(3,3))

        self.get_pos_btn = tk.Button(btn_row1, text="🎯 Track", command=self.toggle_enhanced_mouse_tracking,
                                  bg=COLORS["accent_green"], fg="white", width=11, height=1,
                                  font=("Segoe UI", 7, "bold"), relief="flat", bd=0)
        self.get_pos_btn.pack(side="left", padx=(0,3))
        add_hover_effect(self.get_pos_btn, COLORS["accent_green"], COLORS["hover_green"])

        add_pos_btn = tk.Button(btn_row1, text="Add Position", command=self.add_manual_position,
                               bg=COLORS["accent_blue"], fg="white", width=11, height=1,
                               font=("Segoe UI", 7, "bold"), relief="flat", bd=0)
        add_pos_btn.pack(side="left", padx=(0,3))
        add_hover_effect(add_pos_btn, COLORS["accent_blue"], COLORS["hover_blue"])

        right_side = tk.Frame(main_container, bg=COLORS["bg_card"])
        right_side.pack(side="right", fill="y")

        self.record_unified_btn = tk.Button(right_side, text="⏺️ Record\n(F4)", command=self.toggle_unified_recording,
                                            bg=COLORS["accent_purple"], fg="white", width=12, height=3,
                                            font=("Segoe UI", 8, "bold"), relief="flat", bd=0)
        self.record_unified_btn.pack()
        add_hover_effect(self.record_unified_btn, COLORS["accent_purple"], COLORS["hover_purple"])

        recorded_section = tk.Frame(main, bg=COLORS["bg_card"], relief="flat", bd=1)
        recorded_section.pack(fill="x", pady=(0,5))

        tk.Label(recorded_section, text="🎬 Recorded", fg=COLORS["accent_purple"],
                bg=COLORS["bg_card"], font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=10, pady=(5,3))

        self.recorded_unified_text = scrolledtext.ScrolledText(recorded_section, height=3,
                                              bg=COLORS["bg_accent"], fg=COLORS["text_primary"],
                                              font=("Consolas", 7), relief="flat", bd=0,
                                              selectbackground=COLORS["accent_purple"],
                                              selectforeground="white",
                                              insertbackground=COLORS["accent_purple"])
        self.recorded_unified_text.pack(fill="x", padx=10, pady=(0,3))
        self.recorded_unified_text.config(state=tk.DISABLED)

        recorded_btn_frame = tk.Frame(recorded_section, bg=COLORS["bg_card"])
        recorded_btn_frame.pack(fill="x", padx=10, pady=(0,5))

        add_recorded_btn = tk.Button(recorded_btn_frame, text="✓ Add",
                                    command=self.add_recorded_events_to_actions,
                                    bg=COLORS["accent_green"], fg="white", width=14, height=1,
                                    font=("Segoe UI", 7, "bold"), relief="flat", bd=0)
        add_recorded_btn.pack(side="left", padx=(0,3))
        add_hover_effect(add_recorded_btn, COLORS["accent_green"], COLORS["hover_green"])

        clear_recorded_btn = tk.Button(recorded_btn_frame, text="✗ Clear",
                                      command=self.clear_recorded_events,
                                      bg=COLORS["accent_red"], fg="white", width=8, height=1,
                                      font=("Segoe UI", 7, "bold"), relief="flat", bd=0)
        clear_recorded_btn.pack(side="left")
        add_hover_effect(clear_recorded_btn, COLORS["accent_red"], COLORS["hover_red"])

        list_section = tk.Frame(main, bg=COLORS["bg_card"], relief="flat", bd=1)
        list_section.pack(fill="both", expand=True, pady=(0,5))

        tk.Label(list_section, text="📋 Actions", fg=COLORS["accent_blue"],
                bg=COLORS["bg_card"], font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=9, pady=(5,3))

        list_btn_frame = tk.Frame(list_section, bg=COLORS["bg_card"])
        list_btn_frame.pack(fill="x", padx=10, pady=(0,5))

        save_btn = tk.Button(list_btn_frame, text="💾", command=self.save_positions,
                            bg=COLORS["transparent"], fg="white", width=5, height=1,
                            font=("Segoe UI", 8, "bold"), relief="flat", bd=0)
        save_btn.pack(side="left", padx=(0,3))
        add_hover_effect(save_btn, COLORS["transparent"], COLORS["hover"], transparent=True)

        load_btn = tk.Button(list_btn_frame, text="📂", command=self.load_positions,
                            bg=COLORS["transparent"], fg="white", width=5, height=1,
                            font=("Segoe UI", 8, "bold"), relief="flat", bd=0)
        load_btn.pack(side="left", padx=(0,3))
        add_hover_effect(load_btn, COLORS["transparent"], COLORS["hover"], transparent=True)

        clear_btn = tk.Button(list_btn_frame, text="Clear", command=self.on_clear,
                             bg=COLORS["accent_orange"], fg="white", width=6, height=1,
                             font=("Segoe UI", 8, "bold"), relief="flat", bd=0)
        clear_btn.pack(side="left", padx=(0,3))
        add_hover_effect(clear_btn, COLORS["accent_orange"], COLORS["hover_orange"])

        delete_btn = tk.Button(list_btn_frame, text="❌", command=self.delete_position,
                              bg=COLORS["accent_red"], fg="white", width=5, height=1,
                              font=("Segoe UI", 8, "bold"), relief="flat", bd=0)
        delete_btn.pack(side="left")
        add_hover_effect(delete_btn, COLORS["accent_red"], COLORS["hover_red"])

        self.pos_text = scrolledtext.ScrolledText(list_section, height=3,
                                              bg=COLORS["bg_accent"], fg=COLORS["text_primary"],
                                              font=("Consolas", 7), relief="flat", bd=0,
                                              selectbackground=COLORS["accent_blue"],
                                              selectforeground="white",
                                              insertbackground=COLORS["accent_blue"])
        self.pos_text.pack(fill="both", expand=True, padx=10, pady=(0,5))

        ctrl_section = tk.Frame(main, bg=COLORS["bg_main"])
        ctrl_section.pack(fill="x", pady=(0,5))

        main_controls = tk.Frame(ctrl_section, bg=COLORS["bg_main"])
        main_controls.pack()

        self.start_btn = tk.Button(main_controls, text="▶️(F2)", command=self.on_start,
                               bg=COLORS["accent_green"], fg="white", width=12, height=1,
                               font=("Segoe UI", 8, "bold"), relief="flat", bd=0)
        self.start_btn.pack(side="left", padx=3)
        add_hover_effect(self.start_btn, COLORS["accent_green"], COLORS["hover_green"])

        self.stop_btn = tk.Button(main_controls, text="⏸️(F3)", command=self.on_stop,
                              bg=COLORS["accent_red"], fg="white", width=12, height=1,
                              font=("Segoe UI", 8, "bold"), relief="flat", bd=0)
        self.stop_btn.pack(side="left", padx=3)
        add_hover_effect(self.stop_btn, COLORS["accent_red"], COLORS["hover_red"])

        exit_btn = tk.Button(main_controls, text="🚪(F5)", command=self.on_exit,
                            bg=COLORS["transparent"], fg="white", width=12, height=1,
                            font=("Segoe UI", 8, "bold"), relief="flat", bd=0)
        exit_btn.pack(side="left", padx=3)
        add_hover_effect(exit_btn, COLORS["transparent"], COLORS["hover"], transparent=True)

        status_frame = tk.Frame(main, bg=COLORS["bg_card"], relief="flat", bd=1)
        status_frame.pack(fill="x", pady=5)

        tk.Label(status_frame, text="Status", fg=COLORS["text_secondary"],
                bg=COLORS["bg_card"], font=("Segoe UI", 8)).pack(pady=(5,2))

        self.status_label = tk.Label(status_frame, text="🟢 Ready", fg=COLORS["accent_green"],
                                 bg=COLORS["bg_card"], font=("Segoe UI", 9, "bold"))
        self.status_label.pack(pady=(0,5))

        self.root.bind('<F2>', lambda e: self.on_start())
        self.root.bind('<F3>', lambda e: self.on_stop())
        self.root.bind('<F4>', lambda e: self.toggle_unified_recording())
        self.root.bind('<F5>', lambda e: self.on_exit())
        self.root.bind('<F1>', lambda e: self.show_hide_window())
        self.root.protocol("WM_DELETE_WINDOW", self.on_exit)

        self.root.after(500, self._update_mouse_pos)

    def update_speed_label(self, value=None):
        speed = self.speed_var.get()
        self.speed_label.config(text=f"{speed:.1f}x")
        self.clicker.playback_speed = speed

    def toggle_unified_recording(self):
        """Toggle unified recording (keyboard + mouse movement + mouse clicks)"""
        if self.activation_expired:
            self._handle_expired_activation()
            return

        if not self.unified_recorder.recording:
            self.unified_recorder.start_recording()
            self.record_unified_btn.config(bg=COLORS["accent_red"], text="⏹️ Stop\n(F4)")
            self.status_label.config(text="🎬 Recording", fg=COLORS["accent_purple"])
            play_beep()
        else:
            self.unified_recorder.stop_recording()
            self.record_unified_btn.config(bg=COLORS["accent_purple"], text="⏺️ Record\n(F4)")
            self.status_label.config(text="🟢 Ready", fg=COLORS["accent_green"])
            self.update_unified_display()
            play_beep()

    def update_unified_display(self):
        """Update the unified display showing all recorded events"""
        try:
            events = self.unified_recorder.get_recorded_events()
            self.recorded_unified_text.config(state=tk.NORMAL)
            self.recorded_unified_text.delete(1.0, tk.END)

            if events:
                kb = sum(1 for e in events if e['type'] == 'keyboard')
                cl = sum(1 for e in events if e['type'] == 'mouse_click')
                mv = sum(1 for e in events if e['type'] == 'mouse_move')

                display_text = f"Total:{len(events)} | ⌨️{kb} 🖱️{cl} ↗️{mv}\n"

                for event in events[-8:]:
                    if event['type'] == 'keyboard':
                        display_text += f"⌨️{event['key']}({event['duration']}s) "
                    elif event['type'] == 'mouse_move':
                        display_text += f"↗️({event['dx']},{event['dy']}) "
                    elif event['type'] == 'mouse_click':
                        btn_icon = "L" if event['button'] == 'left' else "R"
                        display_text += f"🖱️{btn_icon}({event['x']},{event['y']}) "

                self.recorded_unified_text.insert(tk.END, display_text)

            self.recorded_unified_text.config(state=tk.DISABLED)
        except Exception as e:
            log_exception(e)

    def add_recorded_events_to_actions(self):
        """Add all recorded events (keyboard + mouse) to actions"""
        if self.activation_expired:
            self._handle_expired_activation()
            return

        events = self.unified_recorder.get_recorded_events()
        if not events:
            show_custom_message("Info", "No events recorded", "info", self.root)
            return

        for event in events:
            if event['type'] == 'keyboard':
                key = event['key']
                duration = event['duration']
                self.clicker.add_keyboard_action("press_release", f"{key}:{duration}", 1)
            elif event['type'] == 'mouse_move':
                dx, dy = event['dx'], event['dy']
                duration = event['duration']
                move_type = event.get('move_type', 'relative')
                self.clicker.add_mouse_movement(dx, dy, duration, move_type)
            elif event['type'] == 'mouse_click':
                x, y = event['x'], event['y']
                button = event['button']
                self.clicker.add_position(x, y, button)

        self.refresh_positions()
        show_custom_message("Success", f"Added {len(events)} events", "success", self.root)

    def clear_recorded_events(self):
        """Clear all recorded events"""
        self.unified_recorder.clear_recorded_events()
        self.update_unified_display()

    def add_manual_position(self):
        if self.activation_expired:
            self._handle_expired_activation()
            return
        try:
            x = int(self.x_entry.get().strip())
            y = int(self.y_entry.get().strip())
            btn = "left"
            self.clicker.add_position(x, y, btn)
            self.refresh_positions()
            self.x_entry.delete(0, tk.END)
            self.y_entry.delete(0, tk.END)
            play_beep()
        except Exception:
            show_custom_message("Error", "Invalid coordinates", "error", self.root)

    def refresh_positions(self):
        try:
            self.pos_text.config(state=tk.NORMAL)
            self.pos_text.delete(1.0, tk.END)

            idx = 1
            for x, y, btn in self.clicker.positions:
                self.pos_text.insert(tk.END, f"{idx:2d}: 🖱️ ({x},{y}) {btn}\n")
                idx += 1

            for dx, dy, duration, move_type in self.clicker.mouse_movements:
                if move_type == "relative":
                    self.pos_text.insert(tk.END, f"{idx:2d}: ↗️ Δ({dx},{dy}) {duration}s\n")
                else:
                    self.pos_text.insert(tk.END, f"{idx:2d}: ↗️ ({dx},{dy}) {duration}s\n")
                idx += 1

            for action_type, value, repeat_count in self.clicker.keyboard_actions:
                if action_type == "press_release" and ":" in value:
                    key_name, duration = value.split(":")
                    self.pos_text.insert(tk.END, f"{idx:2d}: ⌨️ {key_name} ({duration}s)\n")
                else:
                    self.pos_text.insert(tk.END, f"{idx:2d}: ⌨️ {value} x{repeat_count}\n")
                idx += 1

            self.pos_text.config(state=tk.DISABLED)
        except Exception as e:
            log_exception(e)

    def toggle_enhanced_mouse_tracking(self):
        if self.activation_expired:
            self._handle_expired_activation()
            return

        if not self.tracking_mouse:
            self.tracking_mouse = True
            self.get_pos_btn.config(bg=COLORS["accent_red"], text="⏹️ Stop")
            self.status_label.config(text="🎯 Tracking", fg=COLORS["accent_orange"])

            minimize_to_tray(self)
            self.hidden = True

            if self.mouse_tracker.start_tracking():
                pass
            else:
                show_custom_message("Error", "Failed to track", "error", self.root)
                self.cancel_enhanced_mouse_tracking()
        else:
            self.cancel_enhanced_mouse_tracking()

    def add_global_position_silent(self, x, y):
        try:
            btn = "left"
            self.clicker.add_position(x, y, btn)
            self.refresh_positions()
            play_beep()
        except Exception as e:
            log_exception(e)
        finally:
            self.finish_enhanced_mouse_tracking()

    def cancel_enhanced_mouse_tracking(self):
        if self.tracking_mouse:
            self.finish_enhanced_mouse_tracking()

    def finish_enhanced_mouse_tracking(self):
        self.tracking_mouse = False
        self.get_pos_btn.config(bg=COLORS["accent_green"], text="🎯 Track")
        self.mouse_tracker.stop_tracking()

        if self.hidden:
            restore_from_tray(self)
            self.hidden = False

    def _update_mouse_pos(self):
        if not self.tracking_mouse:
            try:
                if HAS_WIN32API and win32api:
                    x, y = win32api.GetCursorPos()
                elif PY_AUTO and pyautogui:
                    x, y = pyautogui.position()
                else:
                    x, y = 0, 0
                self.x_entry.delete(0, tk.END)
                self.x_entry.insert(0, str(x))
                self.y_entry.delete(0, tk.END)
                self.y_entry.insert(0, str(y))
            except Exception:
                pass

        self.root.after(200, self._update_mouse_pos)

    def save_positions(self):
        if self.activation_expired:
            self._handle_expired_activation()
            return
        path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text files", "*.txt"), ("All files", "*.*")], initialfile=POSITIONS_FILE)
        if path:
            if self.clicker.save_positions_txt(path):
                show_custom_message("Success", f"Saved to {path}", "success", self.root)
            else:
                show_custom_message("Error", "Failed to save", "error", self.root)

    def load_positions(self):
        if self.activation_expired:
            self._handle_expired_activation()
            return
        path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt"), ("All files", "*.*")], initialfile=POSITIONS_FILE)
        if path:
            if self.clicker.load_positions_txt(path):
                self.refresh_positions()
                show_custom_message("Success", f"Loaded from {path}", "success", self.root)
            else:
                show_custom_message("Error", "Failed to load", "error", self.root)

    def on_clear(self):
        if self.activation_expired:
            self._handle_expired_activation()
            return
        result = messagebox.askyesno("Confirm", "Clear all?", parent=self.root)
        if result:
            self.clicker.clear_positions()
            self.refresh_positions()

    def delete_position(self):
        if self.activation_expired:
            self._handle_expired_activation()
            return
        try:
            sel = self.pos_text.tag_ranges(tk.SEL)
            if sel:
                text = self.pos_text.get(sel[0], sel[1]).strip()
                if ":" in text:
                    idx_str = text.split(":")[0].strip()
                    try:
                        idx = int(idx_str) - 1
                        total_positions = len(self.clicker.positions)
                        total_movements = len(self.clicker.mouse_movements)

                        if idx < total_positions:
                            self.clicker.remove_position(idx)
                        elif idx < total_positions + total_movements:
                            move_idx = idx - total_positions
                            if 0 <= move_idx < len(self.clicker.mouse_movements):
                                self.clicker.mouse_movements.pop(move_idx)
                                self.clicker.save_positions_txt()
                        else:
                            action_idx = idx - total_positions - total_movements
                            if 0 <= action_idx < len(self.clicker.keyboard_actions):
                                self.clicker.keyboard_actions.pop(action_idx)
                                self.clicker.save_positions_txt()
                        self.refresh_positions()
                    except ValueError:
                        show_custom_message("Warning", "Invalid selection", "warning", self.root)
            else:
                show_custom_message("Warning", "Select a position", "warning", self.root)
        except Exception as e:
            show_custom_message("Warning", "Select a position", "warning", self.root)
            log_exception(e)

    def on_start(self):
        if self.activation_expired:
            self._handle_expired_activation()
            return
        try:
            self.clicker.click_delay = float(self.delay_entry.get() or 0.001)
            self.clicker.keyboard_delay = float(self.kb_delay_entry.get() or 0.001)
            self.clicker.hold_e = bool(self.chk_hold_e_var.get())
            self.clicker.press_enter_enabled = bool(self.chk_enter_var.get())
            self.clicker.press_f_enabled = bool(self.chk_f_var.get())
            self.clicker.press_q_enabled = bool(self.chk_q_var.get())
            self.clicker.press_e_every_minute = bool(self.chk_e_minute_var.get())
            self.clicker.right_click_every_half_second = bool(self.chk_right_click_half_second_var.get())
            self.clicker.playback_speed = self.speed_var.get()
            self.clicker.start()

            self.start_btn.config(state="disabled")
            self.stop_btn.config(state="normal")
            self.status_label.config(text="🟢 Running", fg=COLORS["accent_green"])

            minimize_to_tray(self)
            self.hidden = True

        except Exception as e:
            show_custom_message("Error", f"Failed: {e}", "error", self.root)
            log_exception(e)

    def on_stop(self):
        try:
            self.clicker.stop()
            self.start_btn.config(state="normal")
            self.stop_btn.config(state="disabled")
            self.status_label.config(text="🔴 Stopped", fg=COLORS["accent_red"])

            if self.hidden:
                restore_from_tray(self)
                self.hidden = False

        except Exception as e:
            log_exception(e)
            show_custom_message("Error", f"Error: {e}", "error", self.root)

    def on_exit(self):
        try:
            self.hotkeys.stop()
        except Exception:
            pass
        try:
            self.mouse_tracker.stop_tracking()
        except Exception:
            pass
        try:
            self.unified_recorder.stop_recording()
        except Exception:
            pass
        try:
            self.remote_monitor.stop()
        except Exception:
            pass
        self.clicker.stop()
        try:
            self.root.quit()
            self.root.destroy()
        except Exception:
            pass

    def _update_status_label(self):
        try:
            load_persisted_activation_state()
            current_text = activation_remaining_text()
            username_text = get_username_display()

            self.username_label.config(text=f"👤 {username_text}")
            self.activation_status.config(text=f"⏰ {current_text}")

            if current_text == "EXPIRED" and not self.activation_expired:
                self.activation_expired = True
                self._handle_expired_activation()
            if "EXPIRED" in current_text or "Not activated" in current_text:
                self.activation_status.config(fg=COLORS["accent_red"])
            elif "Activated" in current_text or "lifetime" in current_text:
                self.activation_status.config(fg=COLORS["accent_green"])
            else:
                self.activation_status.config(fg=COLORS["accent_orange"])
        except Exception:
            pass

        self.root.after(2000, self._update_status_label)

    def _handle_expired_activation(self):
        if self.clicker.running:
            self.on_stop()
        show_custom_message("Expired", "Please reactivate", "error", self.root)
        if show_activation_dialog_blocking():
            self.activation_expired = False
            self._update_status_label()
            # Restart remote monitoring if enabled
            if activation_state.get("remote_enabled", False):
                self.remote_monitor.start()
        else:
            self.on_exit()

    def clear_activation(self):
        result = messagebox.askyesno("Confirm", "Clear activation?", parent=self.root)
        if result:
            clear_persisted_activation_state()
            self.activation_expired = True
            show_custom_message("Cleared", "Reactivate required", "info", self.root)
            self._handle_expired_activation()

def main():
    # Initialize Supabase
    init_supabase()

    activated = show_activation_dialog_blocking()
    if not activated:
        return

    try:
        import socket
        lock_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        lock_socket.bind(("localhost", 65432))
    except Exception:
        try:
            root_tmp = tk.Tk()
            root_tmp.withdraw()
            show_custom_message("Error", "Already running", "error")
            root_tmp.destroy()
        except Exception:
            pass
        return

    root = tk.Tk()
    app = MaF1aApp(root)
    try:
        root.mainloop()
    except Exception:
        pass

if __name__ == "__main__":
    main()
