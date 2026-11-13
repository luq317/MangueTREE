import pytest

from manguetree import i18n


@pytest.fixture(autouse=True)
def _clear_i18n_missing():
    i18n.MISSING.clear()
    yield
    i18n.MISSING.clear()
