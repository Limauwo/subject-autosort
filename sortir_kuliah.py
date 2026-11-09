"""Sortir File Kuliah
Memantau folder Downloads. Saat ada file baru, muncul popup untuk memilih
mata kuliah tujuan. Kalau banyak file masuk sekaligus, semuanya digabung
dalam satu popup. Jalan di background dengan ikon di system tray (Windows).
"""
import json
import os
import queue
import shutil
import socket
import sys
import threading
import time
import tkinter as tk
import traceback
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

import pystray
from PIL import Image, ImageDraw
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

try:
    import winreg
except ImportError:  # bukan Windows
    winreg = None

APP_NAME = "SortirFileKuliah"
CONFIG_DIR = Path(os.environ.get("APPDATA", str(Path.home()))) / APP_NAME
CONFIG_FILE = CONFIG_DIR / "config.json"
LOG_FILE = CONFIG_DIR / "log.txt"


def log(msg):
    """Catat ke log.txt (berguna karena versi .exe tidak punya jendela konsol)."""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if LOG_FILE.exists() and LOG_FILE.stat().st_size > 500_000:
            LOG_FILE.write_text("", encoding="utf-8")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")
    except Exception:
        pass


def get_downloads_dir():
    """Cari folder Downloads yang sebenarnya (bisa dipindah ke OneDrive atau drive lain)."""
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            class GUID(ctypes.Structure):
                _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                            ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]

            # FOLDERID_Downloads = {374DE290-123F-4565-9164-39C4925E467B}
            guid = GUID(0x374DE290, 0x123F, 0x4565,
                        (ctypes.c_ubyte * 8)(0x91, 0x64, 0x39, 0xC4, 0x92, 0x5E, 0x46, 0x7B))
            buf = ctypes.c_wchar_p()
            res = ctypes.windll.shell32.SHGetKnownFolderPath(
                ctypes.byref(guid), 0, None, ctypes.byref(buf))
            value = buf.value
            ctypes.windll.ole32.CoTaskMemFree(buf)
            if res == 0 and value:
                return Path(value)
        except Exception:
            pass
    return Path.home() / "Downloads"


DOWNLOADS = get_downloads_dir()
LOCK_PORT = 48653
TEMP_EXT = {".crdownload", ".tmp", ".part", ".download", ".opdownload"}
BATCH_DELAY = 1.5  # detik jeda mengumpulkan file yang datang berdekatan

DEFAULT_CONFIG = {
    "base_folder": str(Path.home() / "Materi"),
    "courses": [
        "BINDO", "DASKOM A", "DASKOM B", "FIDAS", "GAMTEK",
        "KIMDAS", "MATDAS A", "MATDAS B", "PEGANTAR TEKDUS",
    ],
    # Hanya file dengan tipe ini yang memunculkan popup.
    # File lain (installer, video, dll) diabaikan otomatis.
    "extensions": [
        ".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx",
        ".txt", ".zip", ".rar", ".jpg", ".jpeg", ".png",
    ],
    "popup_timeout": 60,  # detik tanpa aktivitas, lalu popup tutup sendiri
}


# ---------- Konfigurasi ----------
def load_config():
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            cfg.update(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return cfg


def save_config(cfg):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


# ---------- Auto-start Windows ----------
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def autostart_command():
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    pyw = Path(sys.executable).with_name("pythonw.exe")
    return f'"{pyw}" "{Path(__file__).resolve()}"'


def is_autostart():
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, APP_NAME)
            return True
    except OSError:
        return False


def set_autostart(enabled):
    if winreg is None:
        return
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if enabled:
            winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, autostart_command())
        else:
            try:
                winreg.DeleteValue(k, APP_NAME)
            except FileNotFoundError:
                pass


# ---------- Utilitas file ----------
def unique_path(dest):
    if not dest.exists():
        return dest
    i = 1
    while True:
        candidate = dest.with_name(f"{dest.stem}_{i}{dest.suffix}")
        if not candidate.exists():
            return candidate
        i += 1


def wait_until_stable(path, checks=3, interval=0.7, timeout=180):
    """Tunggu sampai ukuran file tidak berubah (download selesai)."""
    start = time.time()
    last, stable = -1, 0
    while stable < checks:
        if time.time() - start > timeout or not path.exists():
            return False
        try:
            size = path.stat().st_size
        except OSError:
            return False
        stable = stable + 1 if size == last else 0
        last = size
        time.sleep(interval)
    return True


def short_name(name, limit=58):
    """Singkat nama file panjang tapi pertahankan bagian akhir (ekstensi)."""
    if len(name) <= limit:
        return name
    keep = (limit - 3) // 2
    return name[:keep] + "..." + name[-keep:]


def make_icon():
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((4, 14, 60, 56), radius=8, fill=(37, 99, 235, 255))
    d.rounded_rectangle((4, 8, 30, 22), radius=5, fill=(37, 99, 235, 255))
    d.rectangle((14, 30, 50, 34), fill=(255, 255, 255, 255))
    d.rectangle((14, 40, 40, 44), fill=(255, 255, 255, 255))
    return img


# ---------- Pemantau folder ----------
class Handler(FileSystemEventHandler):
    def __init__(self, app):
        self.app = app

    def on_created(self, event):
        if not event.is_directory:
            self._handle(event.src_path)

    def on_moved(self, event):
        # Browser mengganti nama .crdownload -> nama final; terdeteksi di sini
        if not event.is_directory:
            self._handle(event.dest_path)

    def _handle(self, raw_path):
        app = self.app
        p = Path(raw_path)
        if app.paused:
            log(f"diabaikan (pemantauan dijeda): {p.name}")
            return
        if p.parent != DOWNLOADS:
            return
        ext = p.suffix.lower()
        if ext in TEMP_EXT or p.name.startswith(("~$", ".")):
            return  # file sementara, normal
        if ext not in app.cfg["extensions"]:
            log(f"diabaikan (tipe {ext or '(tanpa ekstensi)'} tidak ada di daftar): {p.name}")
            return  # bukan tipe file materi -> abaikan
        with app.seen_lock:
            if p in app.seen:
                return
            app.seen.add(p)
        log(f"terdeteksi: {p.name}")
        threading.Thread(target=self._wait_then_queue, args=(p,), daemon=True).start()

    def _wait_then_queue(self, p):
        try:
            if wait_until_stable(p):
                self.app.q.put(p)
                self.app.last_put = time.time()
                log(f"siap ditampilkan di popup: {p.name}")
            else:
                log(f"dilewati (file hilang atau tak kunjung selesai): {p.name}")
                self.app.forget(p)
        except Exception:
            log("error di _wait_then_queue:\n" + traceback.format_exc())
            self.app.forget(p)


# ---------- Popup pilih mata kuliah (mendukung banyak file) ----------
class Popup(tk.Toplevel):
    def __init__(self, app, paths):
        super().__init__(app.root)
        self.app = app
        self.items = []   # daftar Path yang sedang ditampilkan
        self.vars = {}    # Path -> BooleanVar (centang)
        self.timeout = int(app.cfg.get("popup_timeout", 60))
        self.remaining = self.timeout

        self.title("File baru di Downloads")
        self.attributes("-topmost", True)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.bind("<Button-1>", self._reset_timer, add="+")

        frm = ttk.Frame(self, padding=12)
        frm.pack()
        for c in range(3):
            frm.columnconfigure(c, weight=1, uniform="col")

        self.header = ttk.Label(frm, font=("Segoe UI", 10, "bold"))
        self.header.grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(frm, text="Centang file yang mau dimasukkan, lalu pilih mata kuliah:",
                  foreground="#555555").grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 4))

        # Daftar file dengan kotak centang (bisa di-scroll)
        list_frame = ttk.Frame(frm)
        list_frame.grid(row=2, column=0, columnspan=3, sticky="ew")
        self.canvas = tk.Canvas(list_frame, width=440, height=60, highlightthickness=0)
        vsb = ttk.Scrollbar(list_frame, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=vsb.set)
        self.inner = ttk.Frame(self.canvas)
        self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>",
                        lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<MouseWheel>", self._wheel)
        self.canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="left", fill="y")

        sel_row = ttk.Frame(frm)
        sel_row.grid(row=3, column=0, columnspan=3, sticky="w", pady=(4, 6))
        ttk.Button(sel_row, text="Pilih semua", command=lambda: self._set_all(True)).pack(side="left")
        ttk.Button(sel_row, text="Kosongkan", command=lambda: self._set_all(False)).pack(
            side="left", padx=(6, 0))

        ttk.Label(frm, text="Masukkan file yang dicentang ke:").grid(
            row=4, column=0, columnspan=3, sticky="w", pady=(0, 4))
        courses = app.cfg["courses"]
        for i, course in enumerate(courses):
            ttk.Button(frm, text=course, command=lambda c=course: self.choose(c)).grid(
                row=5 + i // 3, column=i % 3, sticky="ew", padx=3, pady=3)

        r = 5 + (len(courses) + 2) // 3
        ttk.Separator(frm).grid(row=r, column=0, columnspan=3, sticky="ew", pady=8)
        ttk.Button(frm, text="Bukan materi kuliah (biarkan di Downloads)",
                   command=self.not_course).grid(row=r + 1, column=0, columnspan=3,
                                                 sticky="ew", padx=3, pady=2)
        ttk.Button(frm, text="Jangan tanya lagi untuk tipe file yang dicentang",
                   command=self.never_ask_ext).grid(row=r + 2, column=0, columnspan=3,
                                                   sticky="ew", padx=3, pady=2)
        self.timer_label = ttk.Label(frm, foreground="#666666")
        self.timer_label.grid(row=r + 3, column=0, columnspan=3, pady=(6, 0))

        self.add_files(paths)
        self._tick()

    # --- daftar file ---
    def add_files(self, paths):
        for p in paths:
            if p not in self.vars and p.exists():
                self.items.append(p)
                self.vars[p] = tk.BooleanVar(value=True)
        self._reset_timer()
        self._refresh()

    def _remove(self, paths):
        for p in paths:
            if p in self.vars:
                del self.vars[p]
            if p in self.items:
                self.items.remove(p)
            self.app.forget(p)

    def _selected(self):
        sel = [p for p in self.items if self.vars[p].get()]
        gone = [p for p in sel if not p.exists()]
        if gone:  # file sudah dipindah/dihapus manual
            self._remove(gone)
            self._refresh()
            sel = [p for p in sel if p not in gone]
        return sel

    def _set_all(self, value):
        for v in self.vars.values():
            v.set(value)

    def _wheel(self, event):
        self.canvas.yview_scroll(int(-event.delta / 120), "units")

    def _refresh(self):
        for w in self.inner.winfo_children():
            w.destroy()
        for p in self.items:
            cb = ttk.Checkbutton(self.inner, text=short_name(p.name), variable=self.vars[p])
            cb.pack(anchor="w", pady=1)
            cb.bind("<MouseWheel>", self._wheel)
        n = len(self.items)
        self.header.config(text=f"{n} file baru di Downloads")
        self.canvas.config(height=min(max(n, 1), 7) * 26 + 6)
        self.canvas.yview_moveto(0)
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"+{sw - w - 20}+{sh - h - 80}")

    # --- timer tutup otomatis ---
    def _reset_timer(self, event=None):
        self.remaining = self.timeout

    def _tick(self):
        if not self.winfo_exists():
            return
        if self.remaining <= 0:
            self._close()
            return
        self.timer_label.config(text=f"Ditutup otomatis dalam {self.remaining} detik "
                                     f"(file tetap di Downloads)")
        self.remaining -= 1
        self.after(1000, self._tick)

    def _close(self):
        remaining = list(self.items)
        self.destroy()
        self.app.popup_closed(remaining)

    # --- aksi tombol ---
    def _after_change(self):
        if not self.items:
            self._close()
        else:
            self._refresh()

    def choose(self, course):
        sel = self._selected()
        if not sel:
            messagebox.showinfo("Belum ada file dicentang",
                                "Centang minimal satu file dulu.", parent=self)
            return
        done, errors = self.app.move_files(sel, course)
        self._remove(done)
        if errors:
            detail = "\n".join(f"- {short_name(p.name, 40)}: {msg}" for p, msg in errors[:5])
            extra = f"\n(+{len(errors) - 5} lainnya)" if len(errors) > 5 else ""
            messagebox.showerror("Sebagian file gagal dipindahkan",
                                 f"{detail}{extra}\n\nFile tersebut tetap ada di Downloads.",
                                 parent=self)
        self._after_change()

    def not_course(self):
        sel = self._selected()
        if not sel:
            messagebox.showinfo("Belum ada file dicentang",
                                "Centang file yang bukan materi kuliah dulu.", parent=self)
            return
        self._remove(sel)  # dibiarkan di Downloads
        self._after_change()

    def never_ask_ext(self):
        sel = self._selected()
        if not sel:
            messagebox.showinfo("Belum ada file dicentang",
                                "Centang file dulu untuk menentukan tipenya.", parent=self)
            return
        exts = sorted({p.suffix.lower() for p in sel})
        if not messagebox.askyesno(
                "Jangan tanya lagi?",
                f"Berhenti memunculkan popup untuk tipe file: {', '.join(exts)} ?\n"
                f"(Bisa diaktifkan lagi di Pengaturan)", parent=self):
            return
        for e in exts:
            if e in self.app.cfg["extensions"]:
                self.app.cfg["extensions"].remove(e)
        save_config(self.app.cfg)
        self._remove([p for p in self.items if p.suffix.lower() in exts])
        self._after_change()


# ---------- Aplikasi utama ----------
class App:
    def __init__(self):
        self.cfg = load_config()
        self.first_run = not CONFIG_FILE.exists()
        self.paused = False
        self.q = queue.Queue()        # file baru yang menunggu popup
        self.cmd_q = queue.Queue()    # perintah dari menu tray
        self.last_put = 0.0
        self.seen = set()
        self.seen_lock = threading.Lock()
        self.popup = None
        self.settings_win = None

        self.root = tk.Tk()
        self.root.withdraw()
        self.root.report_callback_exception = (
            lambda *exc: log("error di tampilan:\n" + "".join(traceback.format_exception(*exc))))

        DOWNLOADS.mkdir(parents=True, exist_ok=True)
        self.observer = Observer()
        self.observer.schedule(Handler(self), str(DOWNLOADS), recursive=False)
        self.observer.start()
        log(f"aplikasi berjalan, memantau: {DOWNLOADS} | tipe: {', '.join(self.cfg['extensions'])}")

        menu = pystray.Menu(
            pystray.MenuItem("Jeda pemantauan", self._tray_toggle_pause,
                             checked=lambda item: self.paused),
            pystray.MenuItem("Tes popup",
                             lambda icon, item: self.cmd_q.put("test_popup")),
            pystray.MenuItem("Buka file log",
                             lambda icon, item: self.cmd_q.put("open_log")),
            pystray.MenuItem("Buka folder Downloads",
                             lambda icon, item: self.cmd_q.put("open_downloads")),
            pystray.MenuItem("Pengaturan",
                             lambda icon, item: self.cmd_q.put("settings")),
            pystray.MenuItem("Keluar",
                             lambda icon, item: self.cmd_q.put("quit")),
        )
        self.icon = pystray.Icon(APP_NAME, make_icon(), "Sortir File Kuliah", menu)
        self.icon.run_detached()

        self.root.after(300, self.poll)
        self.root.after(1500, lambda: self.notify(f"Aktif. Memantau: {DOWNLOADS}"))
        if self.first_run:
            self.root.after(600, self.open_settings)

    def run(self):
        self.root.mainloop()

    # --- state ---
    def forget(self, path):
        with self.seen_lock:
            self.seen.discard(path)

    def _tray_toggle_pause(self, icon, item):
        self.paused = not self.paused

    def notify(self, msg):
        try:
            self.icon.notify(msg, "Sortir File Kuliah")
        except Exception:
            pass

    # --- loop utama (thread tkinter) ---
    def poll(self):
        # Selalu jadwalkan ulang, supaya satu error tidak menghentikan pemantauan selamanya
        try:
            if self._poll_once() is False:
                return
        except Exception:
            log("error di poll:\n" + traceback.format_exc())
        self.root.after(300, self.poll)

    def _poll_once(self):
        while not self.cmd_q.empty():
            cmd = self.cmd_q.get()
            if cmd == "settings":
                self.open_settings()
            elif cmd == "open_downloads":
                os.startfile(str(DOWNLOADS))
            elif cmd == "open_log":
                LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
                LOG_FILE.touch(exist_ok=True)
                os.startfile(str(LOG_FILE))
            elif cmd == "test_popup":
                test_file = DOWNLOADS / "tes-popup-sortir.pdf"
                test_file.write_bytes(b"%PDF-1.4 file uji popup Sortir File Kuliah")
                log("membuat file uji: tes-popup-sortir.pdf")
            elif cmd == "quit":
                self.shutdown()
                return False

        # Kumpulkan semua file yang menunggu, setelah arus file baru mereda sebentar
        if not self.q.empty() and time.time() - self.last_put >= BATCH_DELAY:
            paths = []
            while True:
                try:
                    p = self.q.get_nowait()
                except queue.Empty:
                    break
                if p.exists():
                    paths.append(p)
                else:
                    self.forget(p)
            if paths:
                if self.popup is not None and self.popup.winfo_exists():
                    self.popup.add_files(paths)      # tambahkan ke popup yang sedang terbuka
                    log(f"menambah {len(paths)} file ke popup yang terbuka")
                else:
                    self.popup = None
                    try:
                        self.popup = Popup(self, paths)
                        log(f"popup ditampilkan untuk {len(paths)} file")
                    except Exception:
                        log("gagal membuat popup:\n" + traceback.format_exc())
                        for p in paths:
                            self.forget(p)  # supaya file ini bisa terdeteksi lagi nanti

    def popup_closed(self, remaining_paths):
        self.popup = None
        for p in remaining_paths:
            self.forget(p)

    def move_files(self, paths, course):
        """Pindahkan banyak file. Return (daftar_selesai, daftar_error[(path, pesan)])."""
        dest_dir = Path(self.cfg["base_folder"]) / course
        try:
            dest_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            return [], [(p, str(e)) for p in paths]

        done, errors, moved = [], [], 0
        for p in paths:
            if not p.exists():
                done.append(p)  # sudah tidak ada (dipindah/dihapus manual)
                continue
            try:
                shutil.move(str(p), str(unique_path(dest_dir / p.name)))
                done.append(p)
                moved += 1
            except OSError as e:
                errors.append((p, str(e)))
        if moved:
            label = short_name(paths[0].name, 40) if moved == 1 else f"{moved} file"
            self.notify(f"{label} -> {course}")
        return done, errors

    def shutdown(self):
        try:
            self.observer.stop()
            self.icon.stop()
        finally:
            self.root.destroy()

    # --- jendela pengaturan ---
    def open_settings(self):
        if self.settings_win is not None and self.settings_win.winfo_exists():
            self.settings_win.lift()
            return
        win = tk.Toplevel(self.root)
        self.settings_win = win
        win.title("Pengaturan - Sortir File Kuliah")
        win.resizable(False, False)
        win.attributes("-topmost", True)

        frm = ttk.Frame(win, padding=12)
        frm.pack()

        # Folder induk
        base_var = tk.StringVar(value=self.cfg["base_folder"])
        ttk.Label(frm, text="Folder induk mata kuliah (tempat folder BINDO, MATDAS, dst):").grid(
            row=0, column=0, columnspan=2, sticky="w")
        ttk.Entry(frm, textvariable=base_var, width=52).grid(row=1, column=0, sticky="ew")

        def browse():
            d = filedialog.askdirectory(parent=win, initialdir=base_var.get() or str(Path.home()))
            if d:
                base_var.set(str(Path(d)))

        ttk.Button(frm, text="Pilih...", command=browse).grid(row=1, column=1, padx=(6, 0))

        # Daftar mata kuliah
        ttk.Label(frm, text="Daftar mata kuliah (nama = nama folder):").grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(12, 0))
        lb_frame = ttk.Frame(frm)
        lb_frame.grid(row=3, column=0, sticky="ew")
        lb = tk.Listbox(lb_frame, height=9, width=40, exportselection=False)
        sb = ttk.Scrollbar(lb_frame, command=lb.yview)
        lb.config(yscrollcommand=sb.set)
        lb.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")
        for c in self.cfg["courses"]:
            lb.insert("end", c)

        btns = ttk.Frame(frm)
        btns.grid(row=3, column=1, sticky="n", padx=(6, 0))

        def add_course():
            name = simpledialog.askstring("Tambah mata kuliah", "Nama mata kuliah:", parent=win)
            if name and name.strip():
                lb.insert("end", name.strip())

        def remove_course():
            for i in reversed(lb.curselection()):
                lb.delete(i)

        ttk.Button(btns, text="Tambah", command=add_course).pack(fill="x", pady=2)
        ttk.Button(btns, text="Hapus", command=remove_course).pack(fill="x", pady=2)

        # Tipe file
        ttk.Label(frm, text="Tipe file yang memunculkan popup (pisahkan dengan koma):").grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(12, 0))
        ext_var = tk.StringVar(value=", ".join(self.cfg["extensions"]))
        ttk.Entry(frm, textvariable=ext_var, width=52).grid(row=5, column=0, columnspan=2, sticky="ew")

        # Auto-start
        auto_var = tk.BooleanVar(value=is_autostart() if not self.first_run else True)
        ttk.Checkbutton(frm, text="Jalankan otomatis saat Windows menyala",
                        variable=auto_var).grid(row=6, column=0, columnspan=2, sticky="w", pady=(12, 0))

        def save():
            base = base_var.get().strip()
            courses = list(lb.get(0, "end"))
            if not base or not courses:
                messagebox.showwarning("Belum lengkap",
                                       "Folder induk dan minimal satu mata kuliah harus diisi.",
                                       parent=win)
                return
            exts = []
            for e in ext_var.get().split(","):
                e = e.strip().lower()
                if e:
                    exts.append(e if e.startswith(".") else "." + e)
            self.cfg["base_folder"] = base
            self.cfg["courses"] = courses
            self.cfg["extensions"] = exts
            save_config(self.cfg)
            try:
                set_autostart(auto_var.get())
            except OSError:
                messagebox.showwarning("Auto-start gagal",
                                       "Pengaturan disimpan, tapi auto-start tidak bisa diatur.",
                                       parent=win)
            self.first_run = False
            win.destroy()

        ttk.Button(frm, text="Simpan", command=save).grid(
            row=7, column=0, columnspan=2, sticky="e", pady=(14, 0))


def ensure_single_instance():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", LOCK_PORT))
    except OSError:
        return None
    return s


if __name__ == "__main__":
    lock = ensure_single_instance()
    if lock is None:
        tmp = tk.Tk()
        tmp.withdraw()
        messagebox.showinfo("Sortir File Kuliah",
                            "Aplikasi sudah berjalan. Cek ikon di pojok kanan bawah (system tray).")
        sys.exit(0)

    threading.excepthook = lambda a: log(
        "error di thread:\n" + "".join(traceback.format_exception(a.exc_type, a.exc_value, a.exc_traceback)))
    try:
        App().run()
    except Exception:
        log("aplikasi berhenti karena error:\n" + traceback.format_exc())
        try:
            messagebox.showerror(
                "Sortir File Kuliah",
                f"Aplikasi berhenti karena error.\nDetailnya ada di:\n{LOG_FILE}")
        except Exception:
            pass
        raise