"""Live webcam capture and face/eye/iris landmark processing using OpenCV + MediaPipe."""
import time
import cv2
import mediapipe as mp
import numpy as np


class EyeTracker:
    # Face Mesh landmark groups: eye corners, eyelids, and the five iris landmarks.
    EYES = ((33, 133, 159, 145, range(468, 473)), (362, 263, 386, 374, range(473, 478)))

    def __init__(self, camera_index=0):
        self.camera_index = camera_index
        self.capture = None
        self.mesh = None
        self.last = None
        self.fps = 0.0
        self._last_time = time.monotonic()

    def open(self):
        self.capture = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW if hasattr(cv2, "CAP_DSHOW") else 0)
        if not self.capture.isOpened():
            self.capture.release()
            self.capture = None
            raise RuntimeError("Could not open webcam. Check camera permissions or camera index.")
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        try:
            self.mesh = mp.solutions.face_mesh.FaceMesh(max_num_faces=1, refine_landmarks=True,
                min_detection_confidence=0.55, min_tracking_confidence=0.55)
        except AttributeError as exc:
            self.capture.release()
            self.capture = None
            raise RuntimeError("This project uses MediaPipe Face Mesh. Your installed MediaPipe version removed mp.solutions. "
                               "Install the supported version with: python -m pip install mediapipe==0.10.21") from exc

    @staticmethod
    def _point(landmarks, index, width, height):
        p = landmarks[index]
        return np.array([p.x * width, p.y * height], dtype=float)

    def read(self):
        if self.capture is None or self.mesh is None:
            raise RuntimeError("Tracker is not open.")
        ok, frame = self.capture.read()
        if not ok:
            raise RuntimeError("Webcam stopped providing frames.")
        frame = cv2.flip(frame, 1)
        height, width = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = self.mesh.process(rgb)
        now = time.monotonic()
        instant = 1 / max(now - self._last_time, 1e-6)
        self.fps = instant if self.fps == 0 else 0.9 * self.fps + 0.1 * instant
        self._last_time = now
        gaze = None
        confidence = 0.0
        if result.multi_face_landmarks:
            landmarks = result.multi_face_landmarks[0].landmark
            face_mesh = mp.solutions.face_mesh
            face_mesh_module = mp.solutions.drawing_utils
            face_mesh_module.draw_landmarks(frame, result.multi_face_landmarks[0], face_mesh.FACEMESH_CONTOURS,
                                            landmark_drawing_spec=None, connection_drawing_spec=mp.solutions.drawing_styles.get_default_face_mesh_contours_style())
            estimates = []
            for left, right, top, bottom, iris_indices in self.EYES:
                a, b = self._point(landmarks, left, width, height), self._point(landmarks, right, width, height)
                upper, lower = self._point(landmarks, top, width, height), self._point(landmarks, bottom, width, height)
                iris_pts = np.array([self._point(landmarks, i, width, height) for i in iris_indices])
                center = iris_pts.mean(axis=0)
                cv2.circle(frame, tuple(center.astype(int)), 3, (0, 0, 255), -1)
                for p in iris_pts.astype(int):
                    cv2.circle(frame, tuple(p), 2, (0, 255, 255), -1)
                xlo, xhi = sorted((a[0], b[0]))
                ylo, yhi = sorted((upper[1], lower[1]))
                if xhi - xlo > 1 and yhi - ylo > 1:
                    estimates.append(((center[0] - xlo) / (xhi - xlo), (center[1] - ylo) / (yhi - ylo)))
            if estimates:
                gaze = tuple(np.mean(estimates, axis=0))
                confidence = min(1.0, 0.55 + 0.2 * len(estimates))
                cv2.putText(frame, f"Gaze {gaze[0]:.2f}, {gaze[1]:.2f} | confidence {confidence:.2f}", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, .55, (20, 240, 20), 2)
        cv2.putText(frame, f"{self.fps:.1f} FPS", (10, height - 12), cv2.FONT_HERSHEY_SIMPLEX, .55, (20, 240, 20), 2)
        self.last = {"gaze": gaze, "confidence": confidence, "frame": frame, "fps": self.fps,
                     "blink": self._blink(landmarks) if result.multi_face_landmarks else False}
        return self.last

    @staticmethod
    def _blink(landmarks):
        # Blink candidate from average eyelid aperture. Long-blink timing is handled by the UI.
        apertures = []
        for left, right, top, bottom, _iris in EyeTracker.EYES:
            p = lambda i: np.array([landmarks[i].x, landmarks[i].y], dtype=float)
            width = np.linalg.norm(p(left) - p(right))
            if width > 1e-6:
                apertures.append(np.linalg.norm(p(top) - p(bottom)) / width)
        return bool(apertures) and sum(apertures) / len(apertures) < 0.12

    def close(self):
        if self.mesh:
            self.mesh.close()
            self.mesh = None
        if self.capture:
            self.capture.release()
            self.capture = None
