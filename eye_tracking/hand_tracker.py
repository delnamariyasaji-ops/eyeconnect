"""Webcam index-finger and nose tracking for direct prototype cursor control."""
import time

import cv2
import mediapipe as mp


class HandTracker:
    """Track an index fingertip, nose movement, and iris-relative gaze."""

    INDEX_TIP = 8
    EYES = ((33, 133, 159, 145, range(468, 473)),
            (362, 263, 386, 374, range(473, 478)))

    def __init__(self, camera_index=0, hand_enabled=True, face_enabled=True, eye_enabled=False):
        self.camera_index = camera_index
        self.hand_enabled = bool(hand_enabled)
        self.face_enabled = bool(face_enabled)
        self.eye_enabled = bool(eye_enabled)
        self.capture = None
        self.hands = None
        self.face_mesh = None
        self.nose_baseline = None
        self.face_was_visible = False
        self.eye_baseline = None
        self.last_time = time.monotonic()
        self.fps = 0.0

    def open(self):
        backend = cv2.CAP_DSHOW if hasattr(cv2, "CAP_DSHOW") else 0
        self.capture = cv2.VideoCapture(self.camera_index, backend)
        if not self.capture.isOpened():
            self.capture.release()
            self.capture = None
            raise RuntimeError("Could not open webcam. Check camera permissions or camera index.")
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        try:
            self.hands = mp.solutions.hands.Hands(
                static_image_mode=False,
                max_num_hands=1,
                model_complexity=0,
                min_detection_confidence=0.55,
                min_tracking_confidence=0.5,
            )
            self.face_mesh = mp.solutions.face_mesh.FaceMesh(
                static_image_mode=False,
                max_num_faces=1,
                refine_landmarks=True,
                min_detection_confidence=0.55,
                min_tracking_confidence=0.5,
            )
        except AttributeError as exc:
            self.close()
            raise RuntimeError(
                "MediaPipe hand/face tracking could not start. Install the supported version with: "
                ".\\.venv\\Scripts\\python.exe -m pip install mediapipe==0.10.21"
            ) from exc

    def read(self):
        if self.capture is None or self.hands is None or self.face_mesh is None:
            raise RuntimeError("Hand tracker is not open.")
        ok, frame = self.capture.read()
        if not ok:
            raise RuntimeError("Webcam stopped providing frames.")

        # Mirror the preview so moving a finger to the user's right moves the
        # pointer to the right as well.
        frame = cv2.flip(frame, 1)
        height, width = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        hand_result = self.hands.process(rgb) if self.hand_enabled else None
        face_result = self.face_mesh.process(rgb) if self.face_enabled or self.eye_enabled else None
        now = time.monotonic()
        instant = 1.0 / max(now - self.last_time, 1e-6)
        self.fps = instant if self.fps == 0 else 0.9 * self.fps + 0.1 * instant
        self.last_time = now

        finger = None
        if hand_result and hand_result.multi_hand_landmarks:
            hand = hand_result.multi_hand_landmarks[0]
            mp.solutions.drawing_utils.draw_landmarks(
                frame, hand, mp.solutions.hands.HAND_CONNECTIONS
            )
            tip = hand.landmark[self.INDEX_TIP]
            x = min(1.0, max(0.0, float(tip.x)))
            y = min(1.0, max(0.0, float(tip.y)))
            finger = (x, y)
            cv2.circle(frame, (int(x * width), int(y * height)), 10, (0, 255, 255), 3)
            cv2.putText(frame, f"Index fingertip {x:.2f}, {y:.2f}", (10, 28),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (20, 240, 20), 2)
        elif self.hand_enabled:
            cv2.putText(frame, "Show one hand; point with your index finger", (10, 55),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (20, 240, 20), 2)

        nose = None
        head_offset = None
        gaze = None
        eye_offset = None
        if face_result and face_result.multi_face_landmarks:
            landmarks = face_result.multi_face_landmarks[0]
            mp.solutions.drawing_utils.draw_landmarks(
                frame, landmarks, mp.solutions.face_mesh.FACEMESH_CONTOURS
            )
            if self.face_enabled:
                tip = landmarks.landmark[1]
                nose = (min(1.0, max(0.0, float(tip.x))),
                        min(1.0, max(0.0, float(tip.y))))
                if self.nose_baseline is None or not self.face_was_visible:
                    self.nose_baseline = nose
                head_offset = (nose[0] - self.nose_baseline[0],
                               nose[1] - self.nose_baseline[1])
                self.face_was_visible = True
                cv2.circle(frame, (int(nose[0] * width), int(nose[1] * height)), 10, (255, 80, 0), 3)
                cv2.putText(frame, "NOSE", (int(nose[0] * width) + 12, int(nose[1] * height)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 120, 20), 2)

            if self.eye_enabled and len(landmarks.landmark) >= 478:
                gaze_samples = []
                for outer, inner, upper, lower, iris_indices in self.EYES:
                    a, b = landmarks.landmark[outer], landmarks.landmark[inner]
                    top, bottom = landmarks.landmark[upper], landmarks.landmark[lower]
                    iris_points = [landmarks.landmark[index] for index in iris_indices]
                    iris_x = sum(point.x for point in iris_points) / len(iris_points)
                    iris_y = sum(point.y for point in iris_points) / len(iris_points)
                    xlo, xhi = sorted((a.x, b.x))
                    ylo, yhi = sorted((top.y, bottom.y))
                    if xhi - xlo > 1e-4 and yhi - ylo > 1e-4:
                        gaze_samples.append(((iris_x - xlo) / (xhi - xlo),
                                             (iris_y - ylo) / (yhi - ylo)))
                    cv2.circle(frame, (int(iris_x * width), int(iris_y * height)), 5, (40, 255, 40), 2)
                if gaze_samples:
                    gaze = (sum(sample[0] for sample in gaze_samples) / len(gaze_samples),
                            sum(sample[1] for sample in gaze_samples) / len(gaze_samples))
                    if self.eye_baseline is None:
                        self.eye_baseline = gaze
                    eye_offset = (gaze[0] - self.eye_baseline[0],
                                  gaze[1] - self.eye_baseline[1])
                    cv2.putText(frame, f"EYE {eye_offset[0]:+.2f}, {eye_offset[1]:+.2f}", (10, 108),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (40, 255, 40), 2)
        else:
            if self.face_enabled:
                self.face_was_visible = False
            if self.face_enabled or self.eye_enabled:
                hint = "Keep face visible for nose tracking" if self.face_enabled else "Keep both eyes visible for eye tracking"
                cv2.putText(frame, hint, (10, 82),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (20, 240, 20), 2)

        cv2.putText(frame, f"{self.fps:.1f} FPS", (10, height - 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (20, 240, 20), 2)
        return {"finger": finger, "nose": nose, "head_offset": head_offset,
                "gaze": gaze, "eye_offset": eye_offset,
                "frame": frame, "fps": self.fps,
                "hand_detected": finger is not None,
                "face_detected": nose is not None,
                "eye_detected": gaze is not None}

    def close(self):
        if self.face_mesh:
            self.face_mesh.close()
            self.face_mesh = None
        if self.hands:
            self.hands.close()
            self.hands = None
        if self.capture:
            self.capture.release()
            self.capture = None

    def set_hand_enabled(self, enabled):
        self.hand_enabled = bool(enabled)

    def set_face_enabled(self, enabled):
        if not enabled:
            self.face_was_visible = False
            self.nose_baseline = None
        self.face_enabled = bool(enabled)

    def set_eye_enabled(self, enabled):
        if not enabled:
            self.eye_baseline = None
        self.eye_enabled = bool(enabled)
