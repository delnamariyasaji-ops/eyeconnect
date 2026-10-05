import numpy as np


class GazeMapper:
    """Map normalized eye-gaze and optional head-position features to screen pixels."""
    def __init__(self, calibration=None):
        matrix = np.asarray(calibration, dtype=float) if calibration is not None else None
        self.matrix = matrix if matrix is not None and matrix.ndim == 2 and matrix.shape[0] >= 3 and matrix.shape[1] == 2 else None

    def fit(self, feature_points, screen_points):
        features = np.asarray(feature_points, dtype=float)
        screen = np.asarray(screen_points, dtype=float)
        if features.ndim != 2 or screen.ndim != 2 or screen.shape[1] != 2 or len(features) != len(screen):
            raise ValueError("Calibration requires paired feature vectors and 2D screen points.")
        if len(features) < features.shape[1] + 1:
            raise ValueError(f"Calibration needs at least {features.shape[1] + 1} paired samples for these tracking features.")
        design = np.column_stack((features, np.ones(len(features))))
        self.matrix, *_ = np.linalg.lstsq(design, screen, rcond=None)
        return self.matrix.tolist()

    def map(self, features, width, height, sensitivity=1.0):
        if self.matrix is None:
            return None
        values = np.asarray(features, dtype=float).reshape(-1)
        feature_count = self.matrix.shape[0] - 1
        # Older two-feature calibration files still control gaze; recalibrating
        # creates a four-feature model that also learns comfortable head motion.
        values = values[:feature_count]
        if len(values) < feature_count:
            values = np.pad(values, (0, feature_count - len(values)))
        x, y = np.append(values, 1.0) @ self.matrix
        factor = float(np.clip(sensitivity, 0.5, 1.5))
        x = width / 2 + (x - width / 2) * factor
        y = height / 2 + (y - height / 2) * factor
        return (int(np.clip(round(x), 0, width - 1)), int(np.clip(round(y), 0, height - 1)))
