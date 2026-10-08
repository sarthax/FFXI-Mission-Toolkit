"""Transport-neutral, offline-testable live client orchestration.

An external adapter is responsible for version verification and game IO.
No process-memory manipulation is performed by this module.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, Sequence

from .models import ClientSnapshot, DevelopmentAction, PathSample, Position, validate_action


class LiveClientAdapter(Protocol):
    """Opt-in provider; no implicit process discovery or writes."""

    @property
    def supports_writes(self) -> bool: ...

    @property
    def version_verified(self) -> bool: ...

    def snapshot(self) -> ClientSnapshot: ...

    def apply(self, action: DevelopmentAction, parameters: dict) -> None: ...


@dataclass
class LiveClientSession:
    adapter: LiveClientAdapter
    authorized_dev_session: bool = False
    _samples: list[PathSample] = field(default_factory=list, init=False, repr=False)

    def observe(self) -> ClientSnapshot:
        return self.adapter.snapshot()

    def record_sample(self) -> PathSample:
        snapshot = self.observe()
        sample = PathSample(
            observed_at=snapshot.observed_at,
            position=snapshot.position,
            client_id=snapshot.client_id,
        )
        self._samples.append(sample)
        return sample

    def recorded_path(self) -> tuple[PathSample, ...]:
        return tuple(self._samples)

    def execute(self, action: DevelopmentAction, parameters: dict) -> None:
        validate_action(
            action,
            authorized_dev_session=self.authorized_dev_session,
            adapter_supports_writes=self.adapter.supports_writes,
            version_verified=self.adapter.version_verified,
        )
        self.adapter.apply(action, parameters)


@dataclass
class ReplayAdapter:
    """Deterministic fixture for GUI and API development without FFXI."""

    frames: Sequence[ClientSnapshot]
    index: int = 0

    @property
    def supports_writes(self) -> bool:
        return False

    @property
    def version_verified(self) -> bool:
        return False

    def snapshot(self) -> ClientSnapshot:
        if not self.frames:
            raise RuntimeError("replay has no frames")
        return self.frames[min(self.index, len(self.frames) - 1)]

    def advance(self) -> None:
        if self.index + 1 < len(self.frames):
            self.index += 1

    def apply(self, action: DevelopmentAction, parameters: dict) -> None:
        raise PermissionError("replay adapter is read-only")
