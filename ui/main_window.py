"""Accessible EyeConnect desktop application."""
from pathlib import Path
import json
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

from ai.predictor import PhrasePredictor
from eye_tracking.smoothing import ExponentialSmoother
from speech.text_to_speech import SpeechOutput


BASE = Path(__file__).resolve().parents[1]
BG, PANEL, INK, MUTED = "#f2f5f9", "#ffffff", "#172333", "#536275"
BLUE, TEAL, RED, GREEN = "#1769aa", "#00796b", "#b42318", "#1b6e3a"


class EyeConnectApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("EyeConnect — communication made visible")
        self.root.configure(bg=BG)
        self.root.minsize(1050, 720)
        self.root.geometry("1440x900")
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.settings_path = BASE / "data" / "settings.json"
        self.settings = self._load_settings()
        self.predictor = PhrasePredictor(BASE / "data" / "phrases.json", self.settings.get("personalization", {}))
        self.tts = SpeechOutput()
        self.smoother = ExponentialSmoother(self.settings.get("smoothing", .35))
        self.tracker = None
        self.listen_stop_event = None
        self.camera_thread = None
        self.camera_stop = threading.Event()
        self.camera_queue = queue.Queue(maxsize=2)
        self.tracking_features = None
        self.cursor = None
        self.hand_detected = None
        self.dwell_widget = None
        self.dwell_started = None
        self.dwell_fired = False
        self.preview_image = None
        self._build_ui()
        self._refresh_suggestions()
        self.root.after(100, self._poll_camera)
        self.root.after(100, self._dwell_tick)
        self.root.after(2000, self._initial_focus)

    def _load_settings(self):
        try:
            settings = json.loads(self.settings_path.read_text(encoding="utf-8"))
            settings["dwell_seconds"] = max(3.0, float(settings.get("dwell_seconds", 3.0)))
            return settings
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return {"camera_index": 0, "dwell_seconds": 3.0, "smoothing": .35, "sensitivity": 1.0,
                    "font_size": 26, "speech_rate": 155, "blink_click": False, "auto_type": True,
                    "calibration": None, "personalization": {}}

    def _save_settings(self):
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        self.settings_path.write_text(json.dumps(self.settings, indent=2), encoding="utf-8")

    def _style(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", font=("Segoe UI", 13, "bold"), padding=(12, 8))
        style.configure("TScale", background=PANEL)

    def _build_ui(self):
        self._style()
        header = tk.Frame(self.root, bg="#102b46", padx=20, pady=10)
        header.pack(fill="x")
        tk.Label(header, text="EyeConnect", font=("Segoe UI", 25, "bold"), fg="white", bg="#102b46").pack(side="left")
        tk.Label(header, text="HAND TRACKING  ·  COMMUNICATION SUPPORT", font=("Segoe UI", 11, "bold"), fg="#c9d9e8", bg="#102b46").pack(side="left", padx=18, pady=(7, 0))
        self.status_var = tk.StringVar(value="Camera off · use mouse, touch, or index finger")
        tk.Label(header, textvariable=self.status_var, font=("Segoe UI", 11, "bold"), fg="#d9f2ed", bg="#102b46").pack(side="right", pady=(7, 0))

        outer = tk.Frame(self.root, bg=BG, padx=16, pady=13)
        outer.pack(fill="both", expand=True)
        top = tk.Frame(outer, bg=PANEL, padx=12, pady=10, highlightthickness=1, highlightbackground="#d5dde7")
        top.pack(fill="x")
        message_column = tk.Frame(top, bg=PANEL)
        tk.Label(message_column, text="PATIENT MESSAGE · TYPE OR SELECT KEYS", font=("Segoe UI", 11, "bold"), fg=MUTED, bg=PANEL).pack(anchor="w")
        font_size = int(self.settings.get("font_size", 26))
        self.message = tk.Text(message_column, height=3, wrap="word", font=("Segoe UI", font_size, "bold"), fg=INK, bg="#fafdff",
                               relief="flat", padx=10, pady=5, undo=True)
        self.message.pack(fill="x", pady=(5, 0))
        self.message.bind("<KeyRelease>", lambda _e: self._refresh_suggestions())

        # Picture-in-picture panel remains visible beside the message editor,
        # rather than below the scrollable phrase board.
        self.debug_frame = tk.Frame(top, bg="#102b46", padx=8, pady=6)
        tk.Label(self.debug_frame, text="LIVE CAMERA · LANDMARKS", bg="#102b46", fg="#d8e8f4",
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 4))
        self.preview_label = tk.Label(self.debug_frame, bg="#071522", fg="#c9d9e8",
            text="Camera is off\nStart hand tracking to view\nhand and index-finger landmarks", justify="center",
            font=("Segoe UI", 10), width=50, height=16)
        self.preview_label.pack(fill="x")
        self.debug_label = tk.Label(self.debug_frame, bg="#102b46", fg="white", font=("Consolas", 8), justify="left", anchor="w",
                                    text="Waiting for camera…")
        self.debug_label.pack(fill="x", anchor="w", pady=(4, 0))
        self.debug_frame.pack(side="right", fill="y", padx=(10, 0))
        message_column.pack(side="left", fill="both", expand=True)

        controls = tk.Frame(outer, bg=BG)
        controls.pack(fill="x", pady=9)
        self._button(controls, "🔊 SPEAK", self.speak_message, color=TEAL, width=13).pack(side="left", padx=(0, 8))
        self._button(controls, "■ STOP SPEAKING", self.tts.stop, color="#425466", width=17).pack(side="left", padx=5)
        self._button(controls, "⌫ CLEAR", self.clear_message, color="#596b7d", width=12).pack(side="left", padx=5)
        self.camera_button = self._button(controls, "▶ START HAND TRACKING", self.start_camera, color=BLUE, width=24)
        self.camera_button.pack(side="left", padx=(18, 5))
        self.debug_var = tk.BooleanVar(value=True)
        tk.Checkbutton(controls, text="Camera preview", variable=self.debug_var, font=("Segoe UI", 11), bg=BG, command=self._debug_toggle).pack(side="right", padx=4)

        body = tk.PanedWindow(outer, orient="horizontal", bg=BG, sashwidth=7, sashrelief="flat", bd=0)
        body.pack(fill="both", expand=True)
        # Tk Frame padx accepts a single distance; horizontal panel spacing is
        # provided by the PanedWindow sash and the child panel contents.
        left = tk.Frame(body, bg=BG)
        right = tk.Frame(body, bg=BG, width=430)
        body.add(left, minsize=570, stretch="always")
        body.add(right, minsize=390, stretch="always")

        self._section_title(left, "PREDICTIONS", "Choose one to complete or extend the current message")
        self.suggestions_frame = tk.Frame(left, bg=BG)
        self.suggestions_frame.pack(fill="x", pady=(2, 10))
        self._section_title(left, "PATIENT TYPES HERE", "Use the keyboard below, or move the pointer with your index finger")
        keyboard = tk.Frame(left, bg=PANEL, padx=10, pady=10, highlightthickness=1, highlightbackground="#d5dde7")
        keyboard.pack(fill="x")
        self.keyboard_mode = "letters"
        self.keyboard_upper = True
        self.keyboard_rows = tk.Frame(keyboard, bg=PANEL)
        self.keyboard_rows.pack(fill="x")
        self._render_keyboard()
        command_line = tk.Frame(keyboard, bg=PANEL)
        command_line.pack(fill="x", pady=(5, 2))
        self._button(command_line, "ABC", lambda: self._set_keyboard("letters"), color="#d8e8f4", fg=INK, width=6, height=2).pack(side="left", expand=True, fill="x", padx=3)
        self._button(command_line, "123", lambda: self._set_keyboard("numbers"), color="#d8e8f4", fg=INK, width=6, height=2).pack(side="left", expand=True, fill="x", padx=3)
        self._button(command_line, "SYMBOLS", lambda: self._set_keyboard("symbols"), color="#d8e8f4", fg=INK, width=8, height=2).pack(side="left", expand=True, fill="x", padx=3)
        self._button(command_line, "SHIFT", self._shift_keyboard, color="#d8e8f4", fg=INK, width=7, height=2).pack(side="left", expand=True, fill="x", padx=3)
        for label, callback, width in (("SPACE", lambda: self.insert_text(" "), 10), ("BACKSPACE", self.backspace, 12),
                                       ("ENTER", lambda: self.insert_text(". "), 9), ("CLEAR", self.clear_message, 8)):
            self._button(command_line, label, callback, color="#35516b", width=width, height=2).pack(side="left", expand=True, fill="x", padx=3)

        self._section_title(right, "QUICK NEEDS & PHRASES", "Common messages speak aloud when selected")
        self.phrase_tabs = ttk.Notebook(right)
        self.phrase_tabs.pack(fill="both", expand=True)
        self.phrase_buttons = []
        phrases = json.loads((BASE / "data" / "phrases.json").read_text(encoding="utf-8"))
        for category, items in phrases.items():
            tab = tk.Frame(self.phrase_tabs, bg=PANEL, padx=8, pady=8)
            self.phrase_tabs.add(tab, text=category)
            canvas = tk.Canvas(tab, bg=PANEL, highlightthickness=0)
            scrollbar = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
            content = tk.Frame(canvas, bg=PANEL)
            content.bind("<Configure>", lambda _e, c=canvas: c.configure(scrollregion=c.bbox("all")))
            canvas.create_window((0, 0), window=content, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            for n, phrase in enumerate(items):
                color = RED if phrase.upper() == "EMERGENCY" else ("#fff0ed" if category == "Medical" else "#f4f8fb")
                fg = RED if phrase.upper() == "EMERGENCY" else INK
                btn = self._button(content, phrase, lambda p=phrase: self.select_phrase(p), color=color, fg=fg, width=22, height=2)
                btn.grid(row=n // 2, column=n % 2, sticky="nsew", padx=4, pady=4)
                content.grid_columnconfigure(n % 2, weight=1)
                self.phrase_buttons.append(btn)

        self._section_title(right, "CAREGIVER REPLY → PATIENT", "Caregiver can speak a reply or type it below, then speak it aloud")
        listening = tk.Frame(right, bg=PANEL, padx=10, pady=8, highlightthickness=1, highlightbackground="#d5dde7")
        listening.pack(fill="x", pady=(0, 7))
        self.listen_text = tk.Text(listening, height=3, wrap="word", font=("Segoe UI", 17), fg=INK, bg="#fafdff", relief="flat", padx=8, pady=5)
        self.listen_text.pack(fill="x")
        listen_actions = tk.Frame(listening, bg=PANEL)
        listen_actions.pack(fill="x", pady=(7, 0))
        self.listen_start_button = self._button(listen_actions, "🎤 START LISTENING", self.start_listening, color=BLUE, width=18)
        self.listen_start_button.pack(side="left", padx=(0, 6))
        self.listen_stop_button = self._button(listen_actions, "■ STOP", self.stop_listening, color="#536275", width=9)
        self.listen_stop_button.configure(state="disabled")
        self.listen_stop_button.pack(side="left", padx=5)
        self._button(listen_actions, "COPY", self.copy_transcript, color="#536275", width=8).pack(side="left", padx=5)
        self._button(listen_actions, "CLEAR", lambda: self.listen_text.delete("1.0", "end"), color="#536275", width=8).pack(side="left", padx=5)
        self._button(listen_actions, "🔊 SPEAK REPLY", self.speak_reply, color=TEAL, width=14).pack(side="right", padx=(5, 0))

        settings_panel = tk.Frame(right, bg=PANEL, padx=10, pady=7, highlightthickness=1, highlightbackground="#d5dde7")
        settings_panel.pack(fill="x", pady=(1, 0))
        tk.Label(settings_panel, text="ACCESS & TRACKING SETTINGS", font=("Segoe UI", 10, "bold"), fg=MUTED, bg=PANEL).pack(anchor="w")
        row = tk.Frame(settings_panel, bg=PANEL)
        row.pack(fill="x", pady=(3, 0))
        self.dwell_var = tk.DoubleVar(value=float(self.settings.get("dwell_seconds", 3.0)))
        self._labeled_scale(row, "Dwell select (sec)", self.dwell_var, 3.0, 5.0, lambda _v: self._setting_changed("dwell_seconds", self.dwell_var.get())).pack(side="left", expand=True, fill="x", padx=(0, 8))
        self.smoothing_var = tk.DoubleVar(value=float(self.settings.get("smoothing", .35)))
        self._labeled_scale(row, "Smoothing", self.smoothing_var, .1, .9, lambda _v: self._setting_changed("smoothing", self.smoothing_var.get())).pack(side="left", expand=True, fill="x", padx=8)
        self.sensitivity_var = tk.DoubleVar(value=float(self.settings.get("sensitivity", 1.0)))
        self._labeled_scale(row, "Sensitivity", self.sensitivity_var, .5, 1.5, lambda _v: self._setting_changed("sensitivity", self.sensitivity_var.get())).pack(side="left", expand=True, fill="x", padx=8)
        more = tk.Frame(settings_panel, bg=PANEL)
        more.pack(fill="x", pady=(2, 0))
        self.font_size_var = tk.IntVar(value=int(self.settings.get("font_size", 26)))
        self.speech_rate_var = tk.IntVar(value=int(self.settings.get("speech_rate", 155)))
        self._labeled_scale(more, "Message size", self.font_size_var, 18, 40,
                            lambda v: self._setting_changed("font_size", int(float(v)))).pack(side="left", expand=True, fill="x", padx=(0, 8))
        self._labeled_scale(more, "Speech rate", self.speech_rate_var, 110, 210,
                            lambda v: self._setting_changed("speech_rate", int(float(v)))).pack(side="left", expand=True, fill="x", padx=8)
        self.auto_type_var = tk.BooleanVar(value=bool(self.settings.get("auto_type", True)))
        tk.Checkbutton(settings_panel, text="AUTO TYPE suggestions", variable=self.auto_type_var, command=self._toggle_auto_type,
                       font=("Segoe UI", 10), bg=PANEL, fg=INK).pack(anchor="w", pady=(2, 0))
        self._button(settings_panel, "RESET PERSONALIZATION", self.reset_personalization, color="#68798b", width=23, height=1).pack(side="right", pady=3)

        footer = tk.Label(self.root, text="Assistive communication prototype · Not a medical device · Emergency messages do not contact emergency services", bg="#e4eaf1", fg=MUTED, font=("Segoe UI", 9), pady=4)
        footer.pack(fill="x", side="bottom")

    def _section_title(self, parent, title, subtitle):
        line = tk.Frame(parent, bg=BG)
        line.pack(fill="x", pady=(4, 4))
        tk.Label(line, text=title, font=("Segoe UI", 12, "bold"), fg=INK, bg=BG).pack(anchor="w")
        tk.Label(line, text=subtitle, font=("Segoe UI", 9), fg=MUTED, bg=BG).pack(anchor="w")

    def _button(self, parent, label, command, color=BLUE, fg="white", width=16, height=2):
        btn = tk.Button(parent, text=label, command=command, font=("Segoe UI", 12, "bold"), bg=color, fg=fg,
                        activebackground="#dce8f1", activeforeground=INK, relief="flat", bd=0, padx=10, pady=7,
                        width=width, height=height, wraplength=210, cursor="hand2", takefocus=True)
        btn.eye_target = True
        btn.default_bg = color
        btn.bind("<Enter>", lambda _e, b=btn: b.configure(highlightthickness=2, highlightbackground="#00a896"))
        btn.bind("<Leave>", lambda _e, b=btn: b.configure(highlightthickness=0))
        return btn

    def _key(self, parent, label, command):
        return self._button(parent, label, command, color="#e8f0f7", fg=INK, width=4, height=1)

    def _set_keyboard(self, mode):
        self.keyboard_mode = mode
        self._render_keyboard()

    def _shift_keyboard(self):
        self.keyboard_upper = not self.keyboard_upper
        self._render_keyboard()

    def _render_keyboard(self):
        for child in self.keyboard_rows.winfo_children():
            child.destroy()
        if self.keyboard_mode == "numbers":
            rows = ("1234567890", "-/:;()$&@", ".,?!'\"")
        elif self.keyboard_mode == "symbols":
            rows = ("!@#$%^&*()", "[]{}<>+=\\", "~`|:;,.?/")
        else:
            rows = ("QWERTYUIOP", "ASDFGHJKL", "ZXCVBNM")
            if not self.keyboard_upper:
                rows = tuple(row.lower() for row in rows)
        for row in rows:
            line = tk.Frame(self.keyboard_rows, bg=PANEL)
            line.pack(fill="x", pady=3)
            for char in row:
                self._key(line, char, lambda c=char: self.insert_text(c)).pack(side="left", expand=True, fill="x", padx=2)

    def _labeled_scale(self, parent, label, var, start, end, callback):
        frame = tk.Frame(parent, bg=PANEL)
        tk.Label(frame, text=label, font=("Segoe UI", 9, "bold"), bg=PANEL, fg=INK).pack(anchor="w")
        resolution = 1 if isinstance(start, int) and isinstance(end, int) else .05
        tk.Scale(frame, from_=start, to=end, resolution=resolution, orient="horizontal", variable=var, command=callback,
                 showvalue=True, length=105, font=("Segoe UI", 8), bg=PANEL, fg=INK, highlightthickness=0).pack(fill="x")
        return frame

    def _initial_focus(self):
        try:
            self.root.state("zoomed")
        except tk.TclError:
            pass

    def _setting_changed(self, name, value):
        self.settings[name] = float(value)
        if name == "smoothing":
            self.smoother.alpha = max(.05, min(1.0, float(value)))
        elif name == "font_size":
            self.message.configure(font=("Segoe UI", int(value), "bold"))
        self._save_settings()

    def _toggle_auto_type(self):
        self.settings["auto_type"] = bool(self.auto_type_var.get())
        self._save_settings()
        self._refresh_suggestions()

    def _refresh_suggestions(self):
        if not hasattr(self, "suggestions_frame"):
            return
        for child in self.suggestions_frame.winfo_children():
            child.destroy()
        text = self.message.get("1.0", "end-1c")
        suggestions = self.predictor.predict(text)
        if not self.settings.get("auto_type", True):
            suggestions = []
        if not suggestions:
            tk.Label(self.suggestions_frame, text="Suggestions appear here as you type.", bg=BG, fg=MUTED,
                     font=("Segoe UI", 11, "italic")).pack(anchor="w", pady=5)
        for phrase in suggestions:
            btn = self._button(self.suggestions_frame, phrase, lambda p=phrase: self.select_suggestion(p), color="#e5f4f1", fg="#075c50", width=24, height=1)
            btn.pack(side="left", fill="x", expand=True, padx=3, pady=3)

    def _message_value(self):
        return self.message.get("1.0", "end-1c").strip()

    def _replace_message(self, value):
        self.message.delete("1.0", "end")
        self.message.insert("1.0", value)
        self._refresh_suggestions()

    def insert_text(self, value):
        self.message.insert("insert", value)
        self.message.see("insert")
        self._refresh_suggestions()

    def backspace(self):
        try:
            self.message.delete("insert-1c", "insert")
        except tk.TclError:
            pass
        self._refresh_suggestions()

    def clear_message(self):
        self._replace_message("")

    def speak_message(self):
        value = self._message_value()
        if not value:
            self.status_var.set("Type a message before speaking")
            return
        self.tts.speak(value, self.settings.get("speech_rate", 155))
        self.status_var.set("Speaking your message")

    def select_phrase(self, phrase):
        self._replace_message(phrase)
        self._record_selection(phrase)
        self.tts.speak(phrase, self.settings.get("speech_rate", 155))
        self.status_var.set("Phrase selected and spoken")

    def select_suggestion(self, phrase):
        current = self._message_value()
        if phrase.lower().startswith(current.lower()) and len(phrase) > len(current):
            updated = phrase
        elif current and current[-1].isspace():
            updated = current + phrase
        elif current:
            words = current.split()
            updated = " ".join(words[:-1] + [phrase]) if words else phrase
        else:
            updated = phrase
        self._replace_message(updated)
        self._record_selection(phrase)

    def _record_selection(self, phrase):
        weights = self.settings.setdefault("personalization", {})
        key = phrase.lower()
        weights[key] = int(weights.get(key, 0)) + 1
        self.predictor.weights = weights
        self._save_settings()
        self._refresh_suggestions()

    def reset_personalization(self):
        self.settings["personalization"] = {}
        self.predictor.weights = self.settings["personalization"]
        self._save_settings()
        self._refresh_suggestions()
        self.status_var.set("Personalization cleared")

    def start_listening(self):
        if self.listen_stop_event and not self.listen_stop_event.is_set():
            return
        self.listen_stop_event = threading.Event()
        self.status_var.set("Listening for caregiver speech…")
        self.listen_start_button.configure(state="disabled")
        self.listen_stop_button.configure(state="normal")
        stop_event = self.listen_stop_event
        def worker():
            try:
                from speech.speech_to_text import listen_while
                listen_while(stop_event, lambda text: self.root.after(0, lambda t=text: self._append_transcript(t)))
                self.root.after(0, lambda: self._listening_finished("Listening stopped"))
            except Exception as exc:
                self.root.after(0, lambda e=str(exc): self._listening_finished("Speech recognition unavailable: " + e))
        threading.Thread(target=worker, daemon=True).start()

    def stop_listening(self):
        if self.listen_stop_event:
            self.listen_stop_event.set()
            self.status_var.set("Stopping after the current utterance…")

    def _append_transcript(self, text):
        current = self.listen_text.get("1.0", "end-1c").strip()
        self.listen_text.delete("1.0", "end")
        self.listen_text.insert("1.0", (current + "\n" + text.upper()).strip())

    def _listening_finished(self, status):
        self.listen_start_button.configure(state="normal")
        self.listen_stop_button.configure(state="disabled")
        self.status_var.set(status)
        if status.startswith("Speech recognition unavailable:"):
            self.listen_text.delete("1.0", "end")
            self.listen_text.insert("1.0", status)

    def _button_state(self, parent, needle, state):
        for child in parent.winfo_children():
            if isinstance(child, tk.Button) and needle in str(child.cget("text")):
                child.configure(state=state)
            self._button_state(child, needle, state)

    def _listening_done(self, text, error):
        self._button_state(self.root, "LISTEN ONCE", "normal")
        if error:
            self.status_var.set("Speech recognition unavailable")
            self.listen_text.delete("1.0", "end")
            self.listen_text.insert("1.0", "Listening error: " + error)
        else:
            self.listen_text.delete("1.0", "end")
            self.listen_text.insert("1.0", text.upper())
            self.status_var.set("Caregiver speech recognized")

    def copy_transcript(self):
        text = self.listen_text.get("1.0", "end-1c").strip()
        if text:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.status_var.set("Transcript copied")

    def speak_reply(self):
        reply = self.listen_text.get("1.0", "end-1c").strip()
        if not reply:
            self.status_var.set("Type or record a caregiver reply first")
            return
        self.tts.speak(reply, self.settings.get("speech_rate", 155))
        self.status_var.set("Speaking caregiver reply to the patient")

    def start_camera(self):
        if self.camera_thread and self.camera_thread.is_alive():
            self.stop_camera()
            return
        self.camera_stop.clear()
        self.status_var.set("Opening webcam and loading hand tracking…")
        self._set_camera_button("■ STOP HAND TRACKING")
        def worker():
            try:
                from eye_tracking.hand_tracker import HandTracker
                tracker = HandTracker(int(self.settings.get("camera_index", 0)))
                tracker.open()
                self.tracker = tracker
                while not self.camera_stop.is_set():
                    data = tracker.read()
                    try:
                        self.camera_queue.put_nowait(data)
                    except queue.Full:
                        try:
                            self.camera_queue.get_nowait()
                        except queue.Empty:
                            pass
                        self.camera_queue.put_nowait(data)
            except Exception as exc:
                self.root.after(0, lambda e=str(exc): self._camera_error(e))
            finally:
                if self.tracker:
                    self.tracker.close()
                    self.tracker = None
        self.camera_thread = threading.Thread(target=worker, daemon=True)
        self.camera_thread.start()

    def _set_camera_button(self, label):
        self.camera_button.configure(text=label)

    def _camera_error(self, error):
        self._set_camera_button("▶ START HAND TRACKING")
        self.status_var.set("Camera/hand tracking unavailable")
        messagebox.showerror("Hand tracking could not start", error + "\n\nInstall requirements and allow webcam access, then try again.")

    def stop_camera(self):
        self.camera_stop.set()
        self._set_camera_button("▶ START HAND TRACKING")
        self.status_var.set("Hand tracking stopped")
        self.tracking_features = None
        self.smoother.reset()
        self.cursor = None
        self.hand_detected = None
        self.dwell_widget = None
        self.dwell_started = None
        self.dwell_fired = False

    def _poll_camera(self):
        latest = None
        while True:
            try:
                latest = self.camera_queue.get_nowait()
            except queue.Empty:
                break
        if latest:
            finger = latest.get("finger")
            detected = finger is not None
            if detected != self.hand_detected:
                self.hand_detected = detected
                self.status_var.set("Hand detected · move your index finger" if detected
                                    else "Show one hand and point with your index finger")
            if finger is not None:
                self.tracking_features = self.smoother.update(finger)
                screen_width = self.root.winfo_screenwidth()
                screen_height = self.root.winfo_screenheight()
                sensitivity = max(.5, min(1.5, float(self.settings.get("sensitivity", 1.0))))
                x = .5 + (self.tracking_features[0] - .5) * sensitivity
                y = .5 + (self.tracking_features[1] - .5) * sensitivity
                self.cursor = (int(max(0, min(screen_width - 1, round(x * (screen_width - 1))))),
                               int(max(0, min(screen_height - 1, round(y * (screen_height - 1))))))
                try:
                    import pyautogui
                    pyautogui.moveTo(*self.cursor, duration=0)
                except Exception:
                    pass
            else:
                self.tracking_features = None
                self.cursor = None
                self.smoother.reset()
                self.dwell_widget = None
                self.dwell_started = None
                self.dwell_fired = False
            self._update_debug(latest)
        self.root.after(100, self._poll_camera)

    def _update_debug(self, data):
        if not self.debug_var.get():
            return
        pos = self.cursor
        finger = self.tracking_features
        self.debug_label.configure(text=(f"HAND TRACKING\nIndex finger: {'detected' if data.get('hand_detected') else 'not detected'}\n"
             f"Finger position: {f'{finger[0]:.3f}, {finger[1]:.3f}' if finger else '—'}\n"
             f"Screen cursor: {pos if pos else 'show your hand'}\nFPS: {data['fps']:.1f}"))
        try:
            from PIL import Image, ImageTk
            rgb = data["frame"][:, :, ::-1]
            image = Image.fromarray(rgb)
            image.thumbnail((400, 300))
            self.preview_image = ImageTk.PhotoImage(image)
            self.preview_label.configure(image=self.preview_image, text="")
        except Exception:
            pass

    def _debug_toggle(self):
        if not self.debug_var.get():
            self.debug_frame.pack_forget()
        else:
            self.debug_frame.pack(side="right", fill="y", padx=(10, 0))

    def _dwell_tick(self):
        if self.cursor:
            try:
                target = self.root.winfo_containing(*self.cursor)
                while target is not None and not getattr(target, "eye_target", False):
                    target = getattr(target, "master", None)
                if target is not self.dwell_widget:
                    self.dwell_widget, self.dwell_started, self.dwell_fired = target, time.monotonic(), False
                    if target is not None:
                        self.status_var.set(f"Focus: {str(target.cget('text'))[:35]} · dwell to select")
                elif target is not None and not self.dwell_fired:
                    elapsed = time.monotonic() - (self.dwell_started or time.monotonic())
                    progress = min(1.0, elapsed / max(3.0, float(self.settings.get("dwell_seconds", 3.0))))
                    if target.cget("state") == "normal":
                        target.configure(highlightthickness=3, highlightbackground="#f0aa00", activebackground="#ffdc73")
                    self.status_var.set(f"Dwell selection {int(progress * 100)}%")
                    if progress >= 1:
                        self._dwell_activate()
            except tk.TclError:
                pass
        self.root.after(100, self._dwell_tick)

    def _dwell_activate(self):
        target = self.dwell_widget
        if target is None or self.dwell_fired:
            return
        self.dwell_fired = True
        try:
            target.invoke()
        except (tk.TclError, AttributeError):
            pass

    def close(self):
        self.camera_stop.set()
        self.tts.stop()
        self.root.destroy()

    def run(self):
        self.root.mainloop()
