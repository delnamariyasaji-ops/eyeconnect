from pathlib import Path
import json


class PhrasePredictor:
    def __init__(self, phrase_path, personalization=None):
        self.phrases = json.loads(Path(phrase_path).read_text(encoding="utf-8"))
        self.weights = personalization if personalization is not None else {}
        self.common = ["water", "food", "help", "medicine", "rest", "the bathroom", "hungry", "thirsty",
                       "tired", "in pain", "cold", "hot", "okay", "uncomfortable"]

    def predict(self, text, limit=5):
        prefix = text.strip().lower()
        pool = []
        if not prefix:
            pool = list(self.phrases.get("Basic Needs", [])) + list(self.phrases.get("Social", []))
        elif prefix in ("i need", "i need "):
            pool = ["I need " + item for item in self.common[:6]]
        elif prefix in ("i am", "i am ", "i'm", "i'm "):
            pool = ["I am " + item for item in self.common[6:]]
        else:
            for values in self.phrases.values():
                pool.extend(values)
            pool.extend(self.common)
        seen, ranked = set(), []
        for item in pool:
            normalized = item.lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            if normalized.startswith(prefix):
                result = item
            elif prefix and prefix.split()[-1] in normalized:
                result = item
            else:
                continue
            ranked.append((self.weights.get(normalized, 0), result))
        ranked.sort(key=lambda x: -x[0])
        return [item for _score, item in ranked[:limit]]
