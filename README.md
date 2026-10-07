# EyeConnect

EyeConnect is an accessibility-focused desktop communication prototype for people with motor impairments. The patient can move the pointer with an index finger in front of the webcam, type on a large on-screen keyboard, and speak the composed message aloud. Caregivers can reply by speaking into the microphone or typing a reply for the app to speak.

This is an assistive communication prototype. It is not a medical diagnostic or treatment device. Emergency messages are displayed and spoken by the computer; the prototype does not contact emergency services or caregivers.

## Features

- OpenCV webcam capture and MediaPipe Hands landmarks for the index fingertip.
- Mirrored index-finger cursor control with configurable smoothing and sensitivity, combined with nose-based head movement. Head motion nudges the finger-controlled cursor; face movement can also steer the cursor if the hand leaves view.
- High-contrast keyboard, patient message editor, and categorized quick phrases. Hold the pointer over a key or phrase for at least three seconds to select it.
- Patient text-to-speech and caregiver replies by microphone transcription or typed text-to-speech.
- Local phrase prediction and local personalization counters. No patient communication is uploaded by the predictor.
- Text-to-speech via the operating system voice (pyttsx3).
- Caregiver speech transcription through SpeechRecognition's Google backend. It needs a microphone and an internet connection.
- Separate, resizable large camera preview with hand connections, a highlighted index fingertip and nose, head movement, cursor position, and FPS.

## System requirements

- Windows 10/11, macOS, or Linux desktop with a graphical display.
- Python 3.10–3.12 (64-bit recommended; this project pins MediaPipe 0.10.21 for the Hands `mp.solutions` API).
- Webcam for hand and face tracking; microphone for caregiver speech transcription; speakers/headphones for spoken output.
- Internet is not needed for hand tracking, local phrase suggestions, or TTS. Speech recognition sends audio to the Google recognition service through SpeechRecognition and therefore requires internet access.

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

## Use hand control

1. Allow camera access in Windows and press **Start Hand + Face Tracking**. Show one hand to the webcam and point with your index finger. The preview marks the fingertip and nose.
2. Move your index finger toward the right or left side of the camera view; the pointer follows. Moving your head nudges the pointer in the same direction as well. If your hand leaves the view, head movement can still steer the pointer. No calibration is required.
3. Hold the pointer over a keyboard key, prediction, or phrase for at least three seconds to select it. The dwell interval can be increased in the settings panel.
4. The patient types into **Patient Message** with the on-screen keyboard, then selects **Speak**. A quick phrase can also be selected to speak it immediately.
5. The caregiver can press **Start Listening** and speak a reply; the transcript appears in **Caregiver Reply → Patient**. Or type a reply in that area. Press **Speak Reply** to read it aloud to the patient.

## Caregiver speech

Press **Start Listening**, speak near the microphone, then press **Stop** when finished. Recognition runs through the SpeechRecognition Google backend; microphone access and an internet connection are required. The caregiver's transcript appears in the reply area and can be edited, copied, cleared, or spoken aloud using **Speak Reply**.

## Prediction and privacy

Suggestions come from the local phrase set in `data/phrases.json` and a small built-in vocabulary. Selecting phrases increments local frequency counts in `data/settings.json`, which influence future rankings. **Reset Personalization** clears those counts. No LLM service is called. The speech-to-text service is the exception: it sends captured audio to Google for recognition.

## Troubleshooting

- **Camera does not open:** close other apps using the webcam, confirm OS permissions, then try camera index 1 in settings.
- **Hand, fingertip, or nose not detected:** improve lighting and keep your hand and face visible in the camera preview.
- **`mediapipe` has no attribute `solutions`:** install the pinned version inside the virtual environment with `.\.venv\Scripts\python.exe -m pip install mediapipe==0.10.21`, then restart EyeConnect.
- **Cursor jitters:** raise the smoothing value and keep the index fingertip visible.
- **Dwell does not select:** keep the finger pointer on one target for at least three seconds without moving outside it.
- **No speech output:** check the OS audio output and installed voices. pyttsx3 uses local system speech engines.
- **Speech-to-text fails:** check microphone permissions, internet, and PyAudio installation. Speech transcription reports errors in the transcript area.
- **Import/dependency errors:** use Python 3.10–3.12, activate the environment, and run `pip install -r requirements.txt`.

## Project layout

```text
eye_connect/
├── main.py
├── ai/                  # local phrase suggestions
├── data/                # phrase library and local settings
├── eye_tracking/        # MediaPipe hand tracking and cursor smoothing
├── speech/              # TTS and caregiver speech recognition
├── ui/                  # Tkinter accessibility interface
├── tests/               # small offline unit tests
├── requirements.txt
└── README.md
```

## Known prototype limits

Finger-to-screen accuracy varies with camera placement, lighting, hand position, and the user. Caregiver transcription depends on an external speech service. The project does not provide an emergency alert integration, patient profiles, wheelchair control, or clinical decision support.

## Future work

Potential extensions include offline multilingual speech recognition, Malayalam, more robust finger tracking, keyboard layouts, caregiver applications, switch input, and evaluated accessibility studies. Any emergency or medical integration would need careful validation and explicit user consent.
