from dataclasses import dataclass


@dataclass(frozen=True)
class Revision:
    value: str

    def short(self) -> str:
        return self.value[:12]

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class KernelVersion:
    value: str

    def __str__(self) -> str:
        return self.value
