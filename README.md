# EyeConnect

EyeConnect is an accessibility-focused desktop communication proof of concept for people with severe motor impairments. It combines a large on-screen keyboard and phrase board with webcam gaze input, locally stored calibration, spoken output, caregiver speech transcription, and local phrase suggestions.

This is an assistive communication prototype. It is not a medical diagnostic or treatment device. Emergency messages are displayed and spoken by the computer; the prototype does not contact emergency services or caregivers.

## Features

- OpenCV webcam capture and MediaPipe Face Mesh landmark tracking for face, eyes, and iris.
- Nine-point eye-and-head calibration saved locally, with an affine mapping and configurable exponential smoothing. Recalibrate after updating if you already have an older eye-only calibration.
- Gaze cursor movement and configurable dwell selection; optional long-blink selection is experimental.
- High-contrast keyboard, large message editor, and categorized quick phrases. Selecting a phrase speaks it.
- Local phrase prediction and local personalization counters. No patient communication is uploaded by the predictor.
- Text-to-speech via the operating system voice (pyttsx3).
- Caregiver speech transcription through SpeechRecognition's Google backend. It needs a microphone and an internet connection.
- Optional camera debug preview with annotated landmarks, normalized gaze, confidence estimate, cursor position, and FPS.
- Compact live camera preview in the right-side corner. Face contours, eye/iris landmarks, and iris centers are drawn over the webcam image; gaze, confidence, and FPS are shown beside it.

## System requirements

- Windows 10/11, macOS, or Linux desktop with a graphical display.
- Python 3.10–3.12 (64-bit recommended; this project pins MediaPipe 0.10.21 because it uses the Face Mesh `mp.solutions` API).
- Webcam for gaze control; microphone for caregiver speech transcription; speakers/headphones for spoken output.
- Internet is not needed for eye tracking, local phrase suggestions, or TTS. Speech recognition sends audio to the Google recognition service through SpeechRecognition and therefore requires internet access.

## Installation

Open a terminal in the `eye_connect` folder and create an isolated environment:

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Using the virtual environment's Python path directly avoids needing to change PowerShell's script execution policy.

If PyAudio installation fails, install the matching PyAudio wheel for your Python version and operating system, then rerun the requirements install. On Linux, install the system PortAudio development package before installing PyAudio.

## Run

The final command in the installation block starts the app.

## Use eye control

1. Allow camera access in the operating system and press **Start Eye Tracking**.
2. Wait for the status to show that the camera and face landmarks are active. If the camera cannot open, check permissions and try changing `camera_index` in `data/settings.json` (often `0` or `1`).
   The right-side camera preview shows the live annotated camera frame and tracking diagnostics.
3. Sit facing the camera with both eyes visible and steady lighting. Press **Calibrate** and follow the yellow dot with your eyes, holding your gaze until it advances through all nine points.
4. After calibration, gaze moves the system pointer. Hold it over a large key, prediction, or phrase for the dwell interval to select it. The interval and smoothing strength are adjustable in the settings panel.
5. Use **Speak** to say a composed sentence, or choose a quick phrase to insert and speak it immediately. The emergency phrase only displays and speaks a message.

Recalibrate if the camera, chair, screen, or seating position changes significantly. Calibration is stored on this device in `data/settings.json`.

## Caregiver speech

Press **Start Listening**, speak near the microphone, then press **Stop** when finished. Recognition runs through the SpeechRecognition Google backend; microphone access and an internet connection are required. The transcript appears in uppercase and can be copied or cleared. This backend can be replaced in `speech/speech_to_text.py`.

## Prediction and privacy

Suggestions come from the local phrase set in `data/phrases.json` and a small built-in vocabulary. Selecting phrases increments local frequency counts in `data/settings.json`, which influence future rankings. **Reset Personalization** clears those counts. No LLM service is called. The speech-to-text service is the exception: it sends captured audio to Google for recognition.

## Troubleshooting

- **Camera does not open:** close other apps using the webcam, confirm OS permissions, then try camera index 1 in settings.
- **Face or iris not detected:** improve front lighting, move closer, remove obstructions, and keep the face inside the frame. The debug preview shows whether landmarks are detected.
- **`mediapipe` has no attribute `solutions`:** install the pinned version inside the virtual environment with `.\.venv\Scripts\python.exe -m pip install mediapipe==0.10.21`, then restart EyeConnect.
- **Cursor jitters:** raise the smoothing value; recalibrate with stable posture and lighting.
- **Dwell selects too early/late:** adjust dwell time. Eye gaze should rest on a target; ordinary blinks are ignored unless optional long-blink click is enabled.
- **No speech output:** check the OS audio output and installed voices. pyttsx3 uses local system speech engines.
- **Speech-to-text fails:** check microphone permissions, internet, and PyAudio installation. Speech transcription reports errors in the transcript area.
- **Import/dependency errors:** use Python 3.10–3.12, activate the environment, and run `pip install -r requirements.txt`.

## Project layout

```text
eye_connect/
├── main.py
├── ai/                  # local phrase suggestions
├── data/                # phrase library and local settings
├── eye_tracking/        # OpenCV, MediaPipe, mapping, smoothing
├── speech/              # TTS and caregiver speech recognition
├── ui/                  # Tkinter accessibility interface
├── tests/               # small offline unit tests
├── requirements.txt
└── README.md
```

## Known prototype limits

Gaze-to-screen accuracy varies with camera placement, lighting, face position, and the user. The displayed tracking-confidence number is a simple landmark-availability estimate, not a clinically validated confidence score. Long-blink click is experimental. Caregiver transcription depends on an external speech service. The project does not provide an emergency alert integration, patient profiles, wheelchair control, or clinical decision support.

## Future work

Potential extensions include offline multilingual speech recognition, Malayalam, more robust individualized gaze models, keyboard layouts, caregiver applications, switch input, and evaluated accessibility studies. Any emergency or medical integration would need careful validation and explicit user consent.
