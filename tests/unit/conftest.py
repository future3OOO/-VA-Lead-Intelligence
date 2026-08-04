from __future__ import annotations

import pytest


@pytest.fixture(scope="session")
def _test_database() -> None:
    """Keep pure unit tests independent from the integration database fixture."""
