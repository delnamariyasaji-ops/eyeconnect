import numpy as np


class GazeMapper:
    """Least-squares affine mapping from normalized binocular gaze to screen pixels."""
    def __init__(self, calibration=None):
        matrix = np.asarray(calibration, dtype=float) if calibration is not None else None
        self.matrix = matrix if matrix is not None and matrix.shape == (3, 2) else None

    def fit(self, gaze_points, screen_points):
        gaze = np.asarray(gaze_points, dtype=float)
        screen = np.asarray(screen_points, dtype=float)
        if len(gaze) < 3 or gaze.shape != (len(screen), 2):
            raise ValueError("Calibration needs at least three paired gaze and screen points.")
        design = np.column_stack((gaze, np.ones(len(gaze))))
        self.matrix, *_ = np.linalg.lstsq(design, screen, rcond=None)
        return self.matrix.tolist()

    def map(self, gaze, width, height, sensitivity=1.0):
        if self.matrix is None:
            return None
        x, y = np.append(np.asarray(gaze, dtype=float), 1.0) @ self.matrix
        factor = float(np.clip(sensitivity, 0.5, 1.5))
        x = width / 2 + (x - width / 2) * factor
        y = height / 2 + (y - height / 2) * factor
        return (int(np.clip(round(x), 0, width - 1)), int(np.clip(round(y), 0, height - 1)))
