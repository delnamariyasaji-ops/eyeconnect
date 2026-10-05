"""Caregiver speech capture. Uses SpeechRecognition's Google backend (internet required)."""
import speech_recognition as sr


def listen_once(timeout=6, phrase_time_limit=15):
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
    return recognizer.recognize_google(audio)


def listen_while(stop_event, on_text):
    """Recognize successive utterances until stopped; invoke on_text for each transcript."""
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        while not stop_event.is_set():
            try:
                audio = recognizer.listen(source, timeout=1, phrase_time_limit=12)
            except sr.WaitTimeoutError:
                continue
            try:
                on_text(recognizer.recognize_google(audio))
            except sr.UnknownValueError:
                continue
