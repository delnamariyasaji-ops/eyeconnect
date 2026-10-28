import threading


class SpeechOutput:
    def __init__(self):
        self.engine = None
        self.lock = threading.Lock()
        self.request_lock = threading.Lock()
        self.request_id = 0

    def _engine(self):
        if self.engine is None:
            import pyttsx3
            self.engine = pyttsx3.init()
        return self.engine

    def speak(self, text, rate=155):
        if not text.strip():
            return
        # Invalidate queued utterances and interrupt an utterance already
        # playing. The request id prevents older worker threads from starting
        # after a newer Speak/Repeat request.
        with self.request_lock:
            self.request_id += 1
            request_id = self.request_id
        if self.engine:
            try:
                self.engine.stop()
            except Exception:
                pass

        def run():
            with self.lock:
                with self.request_lock:
                    if request_id != self.request_id:
                        return
                engine = self._engine()
                engine.setProperty("rate", int(rate))
                engine.say(text)
                engine.runAndWait()
        threading.Thread(target=run, daemon=True).start()

    def stop(self):
        with self.request_lock:
            self.request_id += 1
        if self.engine:
            try:
                self.engine.stop()
            except Exception:
                pass
