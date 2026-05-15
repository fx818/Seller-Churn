"""Base class and result type for all Skills."""
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SkillResult:
    success: bool
    data: dict
    error: str | None = None
    confidence: float = 1.0      # 0.0–1.0
    used_fallback: bool = False
    latency_ms: int = 0


class Skill:
    name: str = "base"
    version: str = "1.0"
    required_inputs: list[str] = []
    optional_inputs: list[str] = []

    def validate(self, inputs: dict) -> tuple[bool, str]:
        missing = [k for k in self.required_inputs if k not in inputs]
        if missing:
            return False, f"Missing required inputs: {missing}"
        return True, ""

    def run(self, inputs: dict) -> SkillResult:
        """Public entry point — validates, times, and delegates to invoke()."""
        ok, msg = self.validate(inputs)
        if not ok:
            return SkillResult(
                success=False, data={}, error=msg,
                confidence=0.0, used_fallback=False, latency_ms=0
            )
        t0 = time.monotonic()
        try:
            result = self.invoke(inputs)
            result.latency_ms = int((time.monotonic() - t0) * 1000)
            return result
        except Exception as exc:
            try:
                result = self.fallback(inputs, exc)
                result.latency_ms = int((time.monotonic() - t0) * 1000)
                return result
            except Exception as fb_exc:
                return SkillResult(
                    success=False, data={},
                    error=f"invoke: {exc} | fallback: {fb_exc}",
                    confidence=0.0, used_fallback=True,
                    latency_ms=int((time.monotonic() - t0) * 1000),
                )

    def invoke(self, inputs: dict) -> SkillResult:
        raise NotImplementedError

    def fallback(self, inputs: dict, error: Exception) -> SkillResult:
        return SkillResult(
            success=False, data={}, error=str(error),
            confidence=0.1, used_fallback=True,
        )
