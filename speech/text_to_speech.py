import threading


class SpeechOutput:
    def __init__(self):
        self.engine = None
        self.lock = threading.Lock()

    def _engine(self):
        if self.engine is None:
            import pyttsx3
            self.engine = pyttsx3.init()
        return self.engine

    def speak(self, text, rate=155):
        if not text.strip():
            return
        def run():
            with self.lock:
                engine = self._engine()
                engine.setProperty("rate", int(rate))
                engine.say(text)
                engine.runAndWait()
        threading.Thread(target=run, daemon=True).start()

    def stop(self):
        if self.engine:
            self.engine.stop()
