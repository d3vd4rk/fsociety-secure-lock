#!/usr/bin/env python3
# Cross-platform, film prop: fsociety-style full-screen takeover
# - Shows fake file scanning/encryption progress
# - Prominent countdown timer with ransom note text
# - Full-screen window, blocks common close actions
# - Secret phrase to unlock early (type it then press Enter)
# - Optional PNG logo (local path or URL) shown prominently
# - On countdown end, auto-dismisses (or can be set to stay)
#
# This is a harmless display-only prop for filming. It does not read, modify,
# or transmit any files.

import os
import sys
import random
import string
import time
from io import BytesIO
from datetime import timedelta
import tkinter as tk
from tkinter import ttk

# Optional dependencies (only needed for PNG logo rendering)
try:
    from PIL import Image, ImageTk  # pip install pillow
except Exception:  # Pillow not available
    Image = None
    ImageTk = None

# ============================ CONFIGURATION ============================
APP_TITLE = "fsociety"
BACKGROUND_COLOR = "#000000"
PRIMARY_TEXT = "#F0F0F0"
ACCENT_TEXT = "#FF3B3B"
SECONDARY_TEXT = "#7AE0A4"
MONO_FONT = ("Consolas" if os.name == "nt" else "Menlo", 12)
BIG_FONT = ("Consolas" if os.name == "nt" else "Menlo", 46, "bold")
MID_FONT = ("Consolas" if os.name == "nt" else "Menlo", 16, "bold")
SMALL_FONT = ("Consolas" if os.name == "nt" else "Menlo", 10)

# Countdown total seconds (adjust for your shot)
COUNTDOWN_SECONDS = 90

# Secret phrase to unlock early (type it and press Enter)
SECRET_PHRASE = "d4rk"

# If True, close automatically when countdown hits 0. If False, stay on final screen.
AUTO_CLOSE_ON_ZERO = True

# Fake file list length and delay
TOTAL_FAKE_FILES = 600
SCAN_INTERVAL_MS = 25  # 25 ms per item ~ 15s total for 600 files

# Glitch text cadence (ms). Set to None to disable
GLITCH_INTERVAL_MS = 700

# Logo configuration: provide a local file path OR a URL. If both None, ASCII header used.
LOGO_PATH = r"C:\Users\user\Desktop\fsociety screen\fsoc"  # e.g., r"C:/Users/you/Desktop/logo.png"
LOGO_URL = "https://i.imgur.com/f1lawMA.png"


MAX_LOGO_WIDTH_RATIO = 0.9  # percentage of right panel width

# ======================================================================


RANSOM_TEXT = (
    "We are fsociety. Your files have been secured with military grade ciphers.\n"
    "To restore access, follow the instructions before the timer reaches zero."\
)

INSTRUCTION_TEXT = (
    "Do not power off your machine.\n"
    "Tampering will be detected.\n"
    "Contact channel: darknet://fsociety/ops\n"
)

def human_time(seconds:int) -> str:
    if seconds < 0:
        seconds = 0
    td = timedelta(seconds=seconds)
    total_seconds = int(td.total_seconds())
    h, rem = divmod(total_seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

class RansomProp:
    def __init__(self, root: tk.Tk, logo_path: str | None = None, logo_url: str | None = None):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.configure(bg=BACKGROUND_COLOR)
        self.root.protocol("WM_DELETE_WINDOW", self._block_close)
        self.root.bind("<Alt-F4>", lambda e: "break")
        self.root.bind("<Escape>", lambda e: "break")
        self.root.bind("<Control-KeyPress-w>", lambda e: "break")
        self.root.bind("<Command-KeyPress-w>", lambda e: "break")  # macOS
        self.root.bind("<F11>", lambda e: "break")  # prevent toggling

        # Capture Enter to validate secret phrase
        self.root.bind("<Return>", self._try_unlock)

        # Fullscreen setup (cross-platform)
        try:
            self.root.attributes("-fullscreen", True)
        except Exception:
            self.root.attributes("-zoomed", True)

        self.countdown_left = COUNTDOWN_SECONDS
        self.secret_buffer = []  # user typing captured silently
        self.logo_path = logo_path or LOGO_PATH
        self.logo_url = logo_url or LOGO_URL
        self.logo_imgtk = None

        self._setup_ui()
        self._start_loops()

    def _setup_ui(self):
        # Grid weights
        self.root.rowconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=0)
        self.root.rowconfigure(2, weight=2)
        self.root.columnconfigure(0, weight=1)
        self.root.columnconfigure(1, weight=1)

        # Left: fake scanner panel
        left = tk.Frame(self.root, bg=BACKGROUND_COLOR)
        left.grid(row=0, column=0, rowspan=3, sticky="nsew", padx=20, pady=20)
        left.rowconfigure(1, weight=1)
        left.columnconfigure(0, weight=1)

        title = tk.Label(left, text="fsociety secure-lock v3.1", fg=SECONDARY_TEXT, bg=BACKGROUND_COLOR, font=MID_FONT)
        title.grid(row=0, column=0, sticky="w")

        self.scan_list = tk.Listbox(left, bg="#0B0B0B", fg=PRIMARY_TEXT, font=MONO_FONT, relief="flat", highlightthickness=1, highlightbackground="#1E1E1E")
        self.scan_list.grid(row=1, column=0, sticky="nsew", pady=(10,10))

        self.progress = ttk.Progressbar(left, orient=tk.HORIZONTAL, mode="determinate")
        self.progress.grid(row=2, column=0, sticky="ew")
        self.progress.configure(maximum=TOTAL_FAKE_FILES, value=0)

        # Right: ransom + timer
        right = tk.Frame(self.root, bg=BACKGROUND_COLOR)
        right.grid(row=0, column=1, rowspan=3, sticky="nsew", padx=20, pady=20)
        right.rowconfigure(0, weight=0)
        right.rowconfigure(1, weight=1)
        right.rowconfigure(2, weight=0)

        # Header area: either PNG logo or ASCII header + mask
        header_frame = tk.Frame(right, bg=BACKGROUND_COLOR)
        header_frame.grid(row=0, column=0, sticky="n", pady=(0,10))

        # Try to load PNG logo; no ASCII fallback
        self._try_load_logo(header_frame)

        self.timer_lbl = tk.Label(right, text=human_time(self.countdown_left), fg=ACCENT_TEXT, bg=BACKGROUND_COLOR, font=BIG_FONT)
        self.timer_lbl.grid(row=1, column=0, sticky="n", pady=(10, 20))

        ransom = tk.Label(right, text=RANSOM_TEXT, fg=PRIMARY_TEXT, bg=BACKGROUND_COLOR, justify="center", font=MID_FONT)
        ransom.grid(row=2, column=0, sticky="n")

        instructions = tk.Label(right, text=INSTRUCTION_TEXT, fg=SECONDARY_TEXT, bg=BACKGROUND_COLOR, justify="center", font=MONO_FONT)
        instructions.grid(row=3, column=0, sticky="n", pady=(10, 0))

        # Hidden secret phrase hint (dim). Keep subtle for crew.
        self.hint = tk.Label(self.root, text="Type secret phrase then press Enter", fg="#333333", bg=BACKGROUND_COLOR, font=SMALL_FONT)
        self.hint.place(relx=0.5, rely=0.98, anchor="s")

        # Global key capture for secret phrase typing
        self.root.bind("<Key>", self._capture_key)

        # Progress fake data
        self.fake_items = self._generate_fake_file_list(TOTAL_FAKE_FILES)
        self.fake_index = 0

        # Style tweaks for progress bar to match theme
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("Horizontal.TProgressbar", troughcolor="#0B0B0B", background=ACCENT_TEXT, bordercolor="#0B0B0B", lightcolor=ACCENT_TEXT, darkcolor=ACCENT_TEXT)

    def _try_load_logo(self, parent: tk.Widget) -> bool:
        # Returns True if a PNG logo was loaded and rendered; otherwise False.
        source = None
        data = None
        if not (self.logo_path or self.logo_url):
            return False
        if Image is None or ImageTk is None:
            print("[info] Pillow not installed. Install with: pip install pillow")
            return False
        try:
            if self.logo_path and os.path.exists(self.logo_path):
                source = f"file:{self.logo_path}"
                with open(self.logo_path, "rb") as f:
                    data = f.read()
            elif self.logo_url:
                import urllib.request
                source = self.logo_url
                # Use a browser-like User-Agent to reduce 429/anti-bot issues
                req = urllib.request.Request(
                    self.logo_url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                    },
                    method="GET",
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = resp.read()
            else:
                return False
            img = Image.open(BytesIO(data)).convert("RGBA")

            # Compute target width based on parent width once it's realized
            parent.update_idletasks()
            pw = max(600, parent.winfo_width() or 800)
            target_w = int(pw * MAX_LOGO_WIDTH_RATIO)
            w, h = img.size
            if w > target_w:
                scale = target_w / float(w)
                img = img.resize((int(w*scale), int(h*scale)), Image.LANCZOS)

            self.logo_imgtk = ImageTk.PhotoImage(img)
            label = tk.Label(parent, image=self.logo_imgtk, bg=BACKGROUND_COLOR)
            label.pack(anchor="n")
            return True
        except Exception as e:
            print(f"[warn] Failed to load logo from {source}: {e}")
            return False

    def _start_loops(self):
        # Scanning loop
        self._scan_tick()
        # Countdown loop
        self._countdown_tick()
        # Glitch loop
        if GLITCH_INTERVAL_MS:
            self._glitch_tick()

    def _scan_tick(self):
        if self.fake_index < len(self.fake_items):
            item = self.fake_items[self.fake_index]
            self.scan_list.insert(tk.END, item)
            self.scan_list.see(tk.END)
            self.fake_index += 1
            self.progress['value'] = self.fake_index
            self.root.after(SCAN_INTERVAL_MS, self._scan_tick)
        else:
            # Loop a short "encrypting" phase after list ends
            self.scan_list.insert(tk.END, "-- initializing cipher cores --")
            self.scan_list.insert(tk.END, "-- mixing entropy pools --")
            self.scan_list.insert(tk.END, "-- sealing vault --")
            self.scan_list.see(tk.END)

    def _countdown_tick(self):
        self.timer_lbl.configure(text=human_time(self.countdown_left))
        if self.countdown_left <= 0:
            self._on_timer_end()
            return
        self.countdown_left -= 1
        self.root.after(1000, self._countdown_tick)

    def _glitch_tick(self):
        # Occasionally flash accent color for timer for drama
        current = self.timer_lbl.cget("fg")
        new_color = SECONDARY_TEXT if current == ACCENT_TEXT else ACCENT_TEXT
        self.timer_lbl.configure(fg=new_color)
        self.root.after(GLITCH_INTERVAL_MS, self._glitch_tick)

    def _on_timer_end(self):
        # Final state
        self.timer_lbl.configure(text="00:00", fg=ACCENT_TEXT)
        self.scan_list.insert(tk.END, "-- lock complete --")
        self.scan_list.insert(tk.END, "status: secured")
        self.scan_list.see(tk.END)

        # Optional auto-close
        if AUTO_CLOSE_ON_ZERO:
            self.root.after(2500, self._safe_exit)

    def _block_close(self):
        # Ignore window close button
        pass

    def _capture_key(self, event: tk.Event):
        # Capture printable characters to buffer for secret phrase
        if event.keysym == "BackSpace":
            if self.secret_buffer:
                self.secret_buffer.pop()
            return
        if len(event.char) == 1 and event.char.isprintable():
            self.secret_buffer.append(event.char)
            # Keep buffer trimmed to plausible phrase length
            max_len = max(32, len(SECRET_PHRASE) + 5)
            if len(self.secret_buffer) > max_len:
                self.secret_buffer = self.secret_buffer[-max_len:]

    def _try_unlock(self, event=None):
        typed = "".join(self.secret_buffer).strip()
        if SECRET_PHRASE in typed:
            self._safe_exit()
        else:
            # Brief visual feedback (shake timer)
            self._shake_widget(self.timer_lbl)

    def _shake_widget(self, widget, shakes=6, distance=4, delay=25):
        # Simple horizontal shake effect
        original = widget.place_info() if widget.winfo_manager() == 'place' else None
        def do_shake(count=0):
            if count >= shakes:
                if original:
                    widget.place_configure(**original)
                return
            dx = distance if count % 2 == 0 else -distance
            x = widget.winfo_x() + dx
            y = widget.winfo_y()
            widget.place(in_=widget.master, x=x, y=y)
            widget.after(delay, lambda: do_shake(count + 1))
        try:
            do_shake(0)
        except Exception:
            pass

    def _safe_exit(self):
        # Restore from fullscreen and close
        try:
            self.root.attributes("-fullscreen", False)
        except Exception:
            pass
        self.root.destroy()

    def _generate_fake_file_list(self, n):
        # Create plausible-looking file paths across drives/platforms
        samples = []
        user = os.environ.get("USERNAME") or os.environ.get("USER") or "user"
        roots = [
            f"C:/Users/{user}/Documents/",
            f"C:/Users/{user}/Pictures/",
            f"C:/Users/{user}/Desktop/",
            f"/home/{user}/Documents/",
            f"/home/{user}/Pictures/",
            f"/Users/{user}/Documents/",
            f"/Users/{user}/Desktop/",
        ]
        exts = [".docx", ".xlsx", ".pdf", ".jpg", ".png", ".mp4", ".zip", ".txt", ".psd", ".pptx"]
        nouns = [
            "invoice", "tax", "project", "backup", "family", "holiday", "wedding", "lecture",
            "draft", "final", "confidential", "budget", "payroll", "client", "design", "thesis",
            "meeting", "notes", "archive", "report"
        ]
        for _ in range(n):
            root = random.choice(roots)
            name = random.choice(nouns) + "_" + ''.join(random.choices(string.ascii_lowercase + string.digits, k=random.randint(3,6)))
            ext = random.choice(exts)
            samples.append(f"encrypting: {root}{name}{ext}")
        return samples


def parse_args_logo():
    # Minimal arg parsing for --logo and --logo-url
    logo_path = None
    logo_url = None
    args = sys.argv[1:]
    def take_value(flag):
        if flag in args:
            i = args.index(flag)
            if i + 1 < len(args):
                return args[i+1]
        return None
    logo_path = take_value("--logo") or os.environ.get("FSOCIETY_LOGO_PATH")
    logo_url = take_value("--logo-url") or os.environ.get("FSOCIETY_LOGO_URL")
    return logo_path, logo_url


def main():
    logo_path, logo_url = parse_args_logo()
    root = tk.Tk()
    app = RansomProp(root, logo_path=logo_path, logo_url=logo_url)
    root.mainloop()


if __name__ == "__main__":
    main()