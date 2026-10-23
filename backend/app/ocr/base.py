"""Internal OCR data structures and provider interface."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Protocol, Tuple


@dataclass(frozen=True)
class OcrTextBlock:
    """Normalized representation of a single text line or block returned by an OCR engine."""

    text: str
    confidence: float
    bbox: Tuple[Tuple[float, float], Tuple[float, float], Tuple[float, float], Tuple[float, float]]

    @property
    def min_x(self) -> float:
        return min(pt[0] for pt in self.bbox)

    @property
    def max_x(self) -> float:
        return max(pt[0] for pt in self.bbox)

    @property
    def min_y(self) -> float:
        return min(pt[1] for pt in self.bbox)

    @property
    def max_y(self) -> float:
        return max(pt[1] for pt in self.bbox)

    @property
    def vertical_center(self) -> float:
        return (self.min_y + self.max_y) / 2.0

    @property
    def horizontal_center(self) -> float:
        return (self.min_x + self.max_x) / 2.0

    @property
    def height(self) -> float:
        return max(1.0, self.max_y - self.min_y)

    @property
    def width(self) -> float:
        return max(1.0, self.max_x - self.min_x)


@dataclass(frozen=True)
class OcrEngineResult:
    """Complete OCR output from an engine invocation."""

    requested_engine: str
    active_engine: str
    fallback_used: bool
    fallback_reason: Optional[str]
    blocks: List[OcrTextBlock] = field(default_factory=list)
    duration_ms: float = 0.0


class OcrProvider(Protocol):
    """Protocol implemented by OCR engine adapters."""

    def extract_text_blocks(
        self,
        rgb_image: object,
        gray_image: Optional[object] = None,
    ) -> OcrEngineResult:
        """Run OCR on an image array and return structured text blocks."""
        ...
