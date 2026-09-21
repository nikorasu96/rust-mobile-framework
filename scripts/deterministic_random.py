"""Stable dependency-free sampling primitives for generated contract checks."""

from __future__ import annotations

import random
from typing import Any


class StableRandom:
    """Sample using only ``Random.random``'s documented compatibility promise."""

    def __init__(self, seed: int):
        self._random = random.Random(seed)

    def chance(self, probability: float) -> bool:
        """Return whether the next stable sample falls below ``probability``."""
        return self._random.random() < probability

    def index(self, stop: int) -> int:
        """Return a stable index in ``range(stop)``."""
        if stop <= 0:
            raise ValueError("stop must be positive")
        return int(self._random.random() * stop)

    def shuffle(self, values: list[Any]) -> None:
        """Shuffle in place with a stable Fisher-Yates implementation."""
        for upper in range(len(values) - 1, 0, -1):
            selected = self.index(upper + 1)
            values[upper], values[selected] = values[selected], values[upper]
