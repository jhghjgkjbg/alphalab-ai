import math
from collections.abc import Sequence

def cosine_similarity(vector1: Sequence[float], vector2: Sequence[float]) -> float | None:
    try:
        if len(vector1) != len(vector2) or not vector1: return None
        dot = sum(float(a) * float(b) for a, b in zip(vector1, vector2)); n1 = math.sqrt(sum(float(a) ** 2 for a in vector1)); n2 = math.sqrt(sum(float(b) ** 2 for b in vector2))
        if not n1 or not n2: return None
        return dot / (n1 * n2)
    except (TypeError, ValueError, OverflowError): return None
