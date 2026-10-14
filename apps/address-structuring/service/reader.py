"""A simple in-memory reader for the upstream address-structuring pipeline."""

from __future__ import annotations

from collections.abc import Generator

from data_structuring.components.readers.base_reader import AddressSample, BaseReader


class ListReader(BaseReader):
    """Yields ``AddressSample`` objects from an in-memory list (one per call)."""

    def __init__(self, samples: list[AddressSample]) -> None:
        self._samples = samples

    def read(self) -> Generator[AddressSample, None, None]:
        yield from self._samples
