import pytest

from manguetree import i18n


@pytest.fixture(autouse=True)
def _clear_i18n_missing():
    i18n.MISSING.clear()
    yield
    i18n.MISSING.clear()


@pytest.fixture(autouse=True)
def _english_ui_in_tests(request, monkeypatch):
    """The app opens in Portuguese (i18n.UI_DEFAULT); the app tests were written
    against the English labels, so they run with English unless marked ``pt_default``."""
    if "pt_default" not in request.keywords:
        monkeypatch.setattr(i18n, "UI_DEFAULT", "en")


import pytest as _pytest


@_pytest.fixture(autouse=True)
def _colonizacao_on(monkeypatch):
    """The colonization page is a preview (hidden unless switched on); tests use it switched on."""
    monkeypatch.setenv("MANGUETREE_COLONIZACAO", "1")
