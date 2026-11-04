import ctypes
try:
    myappid = 'oppositeofnice.frysonic.audioswitcher'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except:
    pass

import winreg
import subprocess
import pystray
from PIL import Image, ImageTk
import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox
import winsound
import threading
import json
import time

if getattr(sys, 'frozen', False):
    BASE_DIR = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

APPDATA_DIR = os.path.join(os.getenv('APPDATA'), "FrySonic")
os.makedirs(APPDATA_DIR, exist_ok=True)
CONFIG_FILE = os.path.join(APPDATA_DIR, "frysonic_config.json")
setup_root = None
speaker_cb = None
headset_cb = None
device_names_global = []
is_startup_enabled = False
icon = None

REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "FrySonic"

SOUND_FILE = r"C:\Windows\Media\Windows Pop-up Blocked.wav"
STATUS_FILE = os.path.join(os.getenv('TEMP'), 'frysonic_status.txt')


def taskbar_is_light():
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        ) as key:
            return winreg.QueryValueEx(key, "SystemUsesLightTheme")[0] == 1
    except OSError:
        return False


def icon_path(device_type):
    name = "speaker" if device_type == "speaker" else "headphones"
    suffix = "" if taskbar_is_light() else "_white"
    return os.path.join(BASE_DIR, f"frysonic_{name}{suffix}.png")


def set_startup(enable):
    global is_startup_enabled
    try:
        target = sys.executable if getattr(
            sys, 'frozen', False) else os.path.abspath(__file__)
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             REG_PATH, 0, winreg.KEY_ALL_ACCESS)
        if enable:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, f'"{target}"')
            is_startup_enabled = True
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass
            is_startup_enabled = False
        winreg.CloseKey(key)
        save_startup_config(is_startup_enabled)
    except Exception as e:
        print(f"Registry error: {e}")


def toggle_startup(icon, item):
    global is_startup_enabled
    new_state = not is_startup_enabled
    set_startup(new_state)


def save_startup_config(status):
    try:
        config_data = {}
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding='utf-8') as f:
                config_data = json.load(f)
        config_data["STARTUP"] = status
        with open(CONFIG_FILE, "w", encoding='utf-8') as f:
            json.dump(config_data, f, indent=4)
    except:
        pass


def get_system_audio_devices():
    fast_cmd = (
        "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
        "Get-AudioDevice -List | Where-Object { $_.Type -eq 'Playback' } "
        "| Select-Object Index, Name | ConvertTo-Json"
    )

    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive",
            "-ExecutionPolicy", "Bypass", "-Command", fast_cmd],
        capture_output=True, text=True, encoding='utf-8', errors='ignore',
        creationflags=subprocess.CREATE_NO_WINDOW
    )

    stdout = result.stdout.strip()

    if not stdout or "Get-AudioDevice" in result.stderr:
        install_cmd = (
            "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; "
            "if (-not (Get-PackageProvider -Name NuGet -ErrorAction SilentlyContinue)) { "
            "    Install-PackageProvider -Name NuGet -MinimumVersion 2.8.5.201 -Scope CurrentUser -Force -Confirm:$false -ErrorAction SilentlyContinue "
            "}; "
            "Set-PSRepository -Name 'PSGallery' -InstallationPolicy Trusted -ErrorAction SilentlyContinue; "
            "if (-not (Get-Module -ListAvailable -Name AudioDeviceCmdlets)) { "
            "    Install-Module -Name AudioDeviceCmdlets -Force -Scope CurrentUser -AllowClobber -Confirm:$false -ErrorAction SilentlyContinue "
            "}; "
        )
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive",
                "-ExecutionPolicy", "Bypass", "-Command", install_cmd],
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive",
                "-ExecutionPolicy", "Bypass", "-Command", fast_cmd],
            capture_output=True, text=True, encoding='utf-8', errors='ignore',
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        stdout = result.stdout.strip()

    if not stdout:
        return []

    try:
        start = min([i for i in [stdout.find(
            '['), stdout.find('{')] if i != -1])
        end = max([stdout.rfind(']'), stdout.rfind('}')])
        clean_json = stdout[start:end+1]

        data = json.loads(clean_json)
        return data if isinstance(data, list) else [data]
    except Exception as e:
        print(f"JSON parsing error: {e}")
        return []


def open_settings_gui():
    global setup_root, speaker_cb, headset_cb, device_names_global
    threading.Thread(target=_async_open_settings, daemon=True).start()


def _async_open_settings():
    global setup_root, speaker_cb, headset_cb, device_names_global
    devices = get_system_audio_devices()
    device_names_global = devices
    if setup_root is not None:
        setup_root.after(0, update_and_show_window)


def update_and_show_window():
    global setup_root, speaker_cb, headset_cb, device_names_global
    if speaker_cb and headset_cb:
        cb_display_list = [
            f"{d['Index']}: {d['Name']}" for d in device_names_global]
        speaker_cb['values'] = cb_display_list
        headset_cb['values'] = cb_display_list
    setup_root.deiconify()
    setup_root.focus_force()


def create_settings_window():
    global setup_root, speaker_cb, headset_cb

    setup_root = tk.Tk()
    setup_root.title("FrySonic - Setup")
    setup_root.configure(bg='#1e1e1e')
    setup_root.attributes("-topmost", True)
    setup_root.resizable(False, False)
    setup_root.protocol("WM_DELETE_WINDOW", setup_root.withdraw)

    window_width, window_height = 400, 260
    screen_width = setup_root.winfo_screenwidth()
    screen_height = setup_root.winfo_screenheight()
    center_x = int(screen_width / 2 - window_width / 2)
    center_y = int(screen_height / 2 - window_height / 2)
    setup_root.geometry(
        f"{window_width}x{window_height}+{center_x}+{center_y}")

    try:
        img = Image.open(icon_path("speaker")).convert("RGBA")
        photo = ImageTk.PhotoImage(img.resize(
            (48, 48), Image.Resampling.LANCZOS))
        setup_root.iconphoto(True, photo)
        setup_root._icon_reference = photo
    except Exception:
        pass

    style = ttk.Style()
    style.theme_use('clam')
    style.configure("TCombobox", fieldbackground="#2d3436", background="#636e72",
                    foreground="white", bordercolor="#1e1e1e", arrowcolor="white")
    style.map("TCombobox", fieldbackground=[
              ('readonly', '#2d3436')], foreground=[('readonly', 'white')])

    setup_root.option_add('*TCombobox*Listbox.background', '#2d3436')
    setup_root.option_add('*TCombobox*Listbox.foreground', 'white')
    setup_root.option_add('*TCombobox*Listbox.selectBackground', '#0984e3')
    setup_root.option_add('*TCombobox*Listbox.selectForeground', 'white')

    tk.Label(setup_root, text="FrySonic Audio Setup", bg='#1e1e1e',
             fg='white', font=("Segoe UI", 12, "bold")).pack(pady=12)

    tk.Label(setup_root, text="Speaker (Output 1):", bg='#1e1e1e',
             fg='#b2bec3', font=("Segoe UI", 9)).pack()
    speaker_var = tk.StringVar()
    speaker_cb = ttk.Combobox(
        setup_root, textvariable=speaker_var, width=48, state="readonly")
    speaker_cb.pack(pady=4)

    tk.Label(setup_root, text="Headset (Output 2):", bg='#1e1e1e',
             fg='#b2bec3', font=("Segoe UI", 9)).pack()
    headset_var = tk.StringVar()
    headset_cb = ttk.Combobox(
        setup_root, textvariable=headset_var, width=48, state="readonly")
    headset_cb.pack(pady=4)

    def save_and_close():
        if speaker_var.get() and headset_var.get():
            config_data = {
                "INDEX_1": speaker_var.get().split(":")[0].strip(),
                "ISIM_1": ":".join(speaker_var.get().split(":")[1:]).strip(),
                "INDEX_2": headset_var.get().split(":")[0].strip(),
                "ISIM_2": ":".join(headset_var.get().split(":")[1:]).strip(),
                "STARTUP": is_startup_enabled
            }
            with open(CONFIG_FILE, "w", encoding='utf-8') as f:
                json.dump(config_data, f, indent=4)

            global INDEX_1, INDEX_2, ISIM_1, ISIM_2
            INDEX_1, ISIM_1 = config_data["INDEX_1"], config_data["ISIM_1"]
            INDEX_2, ISIM_2 = config_data["INDEX_2"], config_data["ISIM_2"]

            setup_root.withdraw()
            threading.Thread(target=show_custom_notification, args=(
                "FrySonic\nSettings saved successfully!",), daemon=True).start()
        else:
            messagebox.showwarning("Warning", "Please select both devices!")

    save_btn = tk.Button(setup_root, text="SAVE SETTINGS", command=save_and_close,
                         bg="#0984e3", fg="white", activebackground="#74b9ff", activeforeground="white",
                         font=("Segoe UI", 9, "bold"), width=20, relief="flat", bd=0)
    save_btn.pack(pady=15)

    if needs_setup:
        open_settings_gui()
    else:
        setup_root.withdraw()


def show_custom_notification(text):
    def play_sound():
        try:
            winsound.PlaySound(
                SOUND_FILE, winsound.SND_FILENAME | winsound.SND_ASYNC)
        except:
            pass
    threading.Thread(target=play_sound, daemon=True).start()

    notif = tk.Tk()
    notif.withdraw()
    top = tk.Toplevel(notif)
    top.overrideredirect(True)
    top.attributes("-topmost", True, "-alpha", 0)
    top.config(bg='black')
    top.wm_attributes("-transparentcolor", "black")

    w, h = 280, 80
    x, y = top.winfo_screenwidth() - w - 20, top.winfo_screenheight() - h - 60
    top.geometry(f"{w}x{h}+{x}+{y}")

    canvas = tk.Canvas(top, width=w, height=h,
                       bg='black', highlightthickness=0)
    canvas.pack()

    points = [25, 0, w-25, 0, w, 0, w, 25, w, h-25, w,
              h, w-25, h, 25, h, 0, h, 0, h-25, 0, 25, 0, 0]
    canvas.create_polygon(points, fill='#2d3436', smooth=True)
    canvas.create_text(w/2, h/2, text=text, fill='white',
                       font=('Segoe UI', 10, 'bold'), justify='center', width=w-40)

    def fade_in(wnd, alpha):
        if alpha < 0.9:
            alpha += 0.1
            wnd.attributes("-alpha", alpha)
            wnd.after(20, lambda: fade_in(wnd, alpha))
        else:
            wnd.after(2000, lambda: fade_out(wnd, alpha))

    def fade_out(wnd, alpha):
        if alpha > 0.0:
            alpha -= 0.1
            wnd.attributes("-alpha", alpha)
            wnd.after(20, lambda: fade_out(wnd, alpha))
        else:
            wnd.master.destroy()

    fade_in(top, 0)
    notif.mainloop()


def toggle_device(icon=None, item=None):
    global INDEX_1, INDEX_2, ISIM_1, ISIM_2, current_type
    try:
        with open(STATUS_FILE, 'r') as f:
            last_index = f.read().strip()
    except Exception:
        last_index = INDEX_2

    if last_index == INDEX_1:
        target_index, target_label, new_icon_type = INDEX_2, ISIM_2, "headphones"
    else:
        target_index, target_label, new_icon_type = INDEX_1, ISIM_1, "speaker"

    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                   "-Command", f"Set-AudioDevice -Index {target_index}"], creationflags=subprocess.CREATE_NO_WINDOW)

    with open(STATUS_FILE, 'w') as f:
        f.write(target_index)
    current_type = new_icon_type
    if icon:
        icon.icon = get_icon_image(new_icon_type)

    threading.Thread(target=show_custom_notification, args=(
        f"FrySonic Switched To:\n{target_label}",), daemon=True).start()


def get_icon_image(device_type):
    try:
        img = Image.open(icon_path(device_type)).convert("RGBA")
        return img.resize((64, 64), Image.Resampling.LANCZOS)
    except Exception:
        return Image.new('RGBA', (64, 64), (255, 0, 0, 255))


def watch_taskbar_theme():
    """Swap the tray icon if the user changes the Windows theme while running."""
    last = taskbar_is_light()
    while True:
        time.sleep(3)
        now = taskbar_is_light()
        if now != last:
            last = now
            if icon is not None:
                icon.icon = get_icon_image(current_type)


def setup_pystray():
    global icon
    icon = pystray.Icon("FrySonic", get_icon_image(start_type), "FrySonic")
    icon.menu = pystray.Menu(
        pystray.MenuItem('🔄 Toggle Device', toggle_device, default=True),
        pystray.MenuItem('⚙️ Settings', open_settings_gui),
        pystray.MenuItem('🚀 Start With Windows', toggle_startup,
                         checked=lambda item: is_startup_enabled),
        pystray.MenuItem('❌ Exit', lambda icon: quit_program())
    )
    icon.run()


def quit_program():
    icon.stop()
    try:
        setup_root.after(0, setup_root.quit)
    except Exception:
        pass


try:
    with open(CONFIG_FILE, "r", encoding='utf-8') as f:
        config = json.load(f)
except Exception:
    config = {}

needs_setup = "INDEX_1" not in config or "INDEX_2" not in config
INDEX_1, ISIM_1 = config.get("INDEX_1", "1"), config.get("ISIM_1", "Speaker")
INDEX_2, ISIM_2 = config.get("INDEX_2", "2"), config.get("ISIM_2", "Headset")
is_startup_enabled = config.get("STARTUP", False)

try:
    with open(STATUS_FILE, 'r') as f:
        s_idx = f.read().strip()
    start_type = "speaker" if s_idx == INDEX_1 else "headphones"
except Exception:
    start_type = "speaker"
current_type = start_type

set_startup(is_startup_enabled)

create_settings_window()
threading.Thread(target=setup_pystray, daemon=True).start()
threading.Thread(target=watch_taskbar_theme, daemon=True).start()
setup_root.mainloop()
