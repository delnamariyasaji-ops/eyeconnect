"""Filter noisy iris offsets into one cardinal cursor direction at a time."""


class CardinalEyeController:
    """Apply a dead zone and axis lock to normalized iris offsets."""

    def __init__(self, deadzone=0.03, release_zone=0.018, confirm_frames=2, axis_ratio=1.15):
        self.deadzone = float(deadzone)
        self.release_zone = float(release_zone)
        self.confirm_frames = max(1, int(confirm_frames))
        self.axis_ratio = float(axis_ratio)
        self.axis = None
        self.candidate_axis = None
        self.candidate_frames = 0
        self.direction = 0

    def reset(self):
        self.axis = None
        self.candidate_axis = None
        self.candidate_frames = 0
        self.direction = 0

    def update(self, offset):
        """Return an offset with at most one nonzero axis, suppressing jitter."""
        if offset is None:
            self.reset()
            return (0.0, 0.0)

        x, y = float(offset[0]), float(offset[1])
        if self.axis is not None:
            value = x if self.axis == "x" else y
            if abs(value) <= self.release_zone:
                self.reset()
                return (0.0, 0.0)
            self.direction = 1 if value >= 0 else -1
            adjusted = self.direction * max(0.0, abs(value) - self.deadzone)
            return (adjusted, 0.0) if self.axis == "x" else (0.0, adjusted)

        abs_x, abs_y = abs(x), abs(y)
        strongest = max(abs_x, abs_y)
        if strongest <= self.deadzone:
            self.candidate_axis = None
            self.candidate_frames = 0
            return (0.0, 0.0)

        # Resolve diagonals to the dominant axis. The ratio dampens small
        # cross-axis fluctuations instead of letting them steer diagonally.
        if abs_x >= abs_y * self.axis_ratio:
            candidate = "x"
        elif abs_y >= abs_x * self.axis_ratio:
            candidate = "y"
        else:
            candidate = "x" if abs_x >= abs_y else "y"

        if candidate == self.candidate_axis:
            self.candidate_frames += 1
        else:
            self.candidate_axis = candidate
            self.candidate_frames = 1
        if self.candidate_frames < self.confirm_frames:
            return (0.0, 0.0)

        self.axis = candidate
        value = x if candidate == "x" else y
        self.direction = 1 if value >= 0 else -1
        adjusted = self.direction * max(0.0, abs(value) - self.deadzone)
        return (adjusted, 0.0) if candidate == "x" else (0.0, adjusted)
