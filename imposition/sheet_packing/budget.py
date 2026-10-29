"""Work limits checked before packing search and output duplication."""

from dataclasses import dataclass, field

LIMITS = dict(
    specs=128,
    instances=1000,
    sheets=256,
    free_rectangles=4096,
    candidates=2_000_000,
    vertices=2_000_000,
    svg_bytes=256 * 1024 * 1024,
)


@dataclass
class PackingBudget:
    limits: dict = field(default_factory=dict)
    used: dict = field(default_factory=dict)

    def __post_init__(self):
        self.limits = LIMITS | self.limits
        if any(type(v) is not int or v < 0 for v in self.limits.values()):
            raise ValueError("budget limits require nonnegative integers")

    def reserve(self, kind, count):
        if kind not in self.limits or type(count) is not int or count < 0:
            raise ValueError("invalid budget charge")
        total = self.used.get(kind, 0) + count
        if total > self.limits[kind]:
            raise ValueError(f"sheet packing {kind} budget exceeded")
        self.used[kind] = total
