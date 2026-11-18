from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from manguetree import i18n

APP = Path(__file__).resolve().parents[1] / "src" / "manguetree" / "app"


@pytest.mark.pt_default
def test_app_opens_in_portuguese():
    at = AppTest.from_file(str(APP / "Home.py"), default_timeout=60).run()
    assert not at.exception
    assert at.sidebar.selectbox[0].value == "pt"
    assert any(i18n.t("home.title", "pt") in m.value for m in at.markdown)


def test_language_options_show_flags_and_portuguese_first():
    assert list(i18n.LANGUAGES) == ["pt", "en"]
    assert i18n.FLAGS["pt"] == "🇧🇷"


def test_menu_names_are_translated():
    for key in ("nav.home", "nav.single", "nav.multiple", "nav.temporal", "nav.about"):
        assert i18n.t(key, "pt") and i18n.t(key, "en")
    assert i18n.t("nav.single", "pt") == "Parcela única"


def test_automatic_menu_is_off():
    for cfg in (APP / ".streamlit" / "config.toml",
                APP.parents[2] / ".streamlit" / "config.toml"):
        assert "showSidebarNavigation = false" in cfg.read_text(encoding="utf-8")
