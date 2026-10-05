import tempfile
import unittest
from pathlib import Path

from ai.predictor import PhrasePredictor
from eye_tracking.gaze_mapper import GazeMapper
from eye_tracking.smoothing import ExponentialSmoother


ROOT = Path(__file__).resolve().parents[1]


class GazeMapperTests(unittest.TestCase):
    def test_affine_mapping_fits_nine_points(self):
        gaze = [(x, y) for y in (0.1, 0.5, 0.9) for x in (0.1, 0.5, 0.9)]
        screen = [(x * 1000, y * 700) for x, y in gaze]
        mapper = GazeMapper()
        mapper.fit(gaze, screen)
        self.assertEqual(mapper.map((0.5, 0.5), 1000, 700), (500, 350))

    def test_requires_three_pairs(self):
        with self.assertRaises(ValueError):
            GazeMapper().fit([(0, 0), (1, 1)], [(0, 0), (1, 1)])


class SmootherTests(unittest.TestCase):
    def test_exponential_smoothing_and_reset(self):
        smoother = ExponentialSmoother(.5)
        self.assertEqual(smoother.update((0, 0)), (0, 0))
        self.assertEqual(smoother.update((1, 1)), (.5, .5))
        smoother.reset()
        self.assertEqual(smoother.update((1, 0)), (1, 0))


class PredictorTests(unittest.TestCase):
    def test_contextual_needs_suggestions(self):
        predictor = PhrasePredictor(ROOT / "data" / "phrases.json")
        result = predictor.predict("I need")
        self.assertIn("I need water", result)
        self.assertIn("I need help", result)

    def test_personalization_ranks_selected_phrase(self):
        predictor = PhrasePredictor(ROOT / "data" / "phrases.json", {"i need water": 8})
        self.assertEqual(predictor.predict("I need")[0], "I need water")


if __name__ == "__main__":
    unittest.main()
