class ExponentialSmoother:
    def __init__(self, alpha=0.35):
        self.alpha = max(0.05, min(1.0, float(alpha)))
        self.value = None

    def update(self, value):
        if self.value is None:
            self.value = tuple(value)
        else:
            self.value = tuple(self.alpha * v + (1 - self.alpha) * old for v, old in zip(value, self.value))
        return self.value

    def reset(self):
        self.value = None
