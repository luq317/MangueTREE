import json
import re
from pathlib import Path

from manguetree import icons

SRC = Path(__file__).resolve().parents[1] / "src" / "manguetree"
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿⭐]")


def test_every_icon_used_by_the_app_exists():
    used = set(icons.NAV_ICONS.values())
    for page in (SRC / "app").rglob("*.py"):
        text = page.read_text(encoding="utf-8")
        for block in re.findall(r"tab_icons=\(([^)]*)\)", text):
            used |= set(re.findall(r'"(\w+)"', block))
        used |= set(re.findall(r'icon_(?:heading|note)\([^,]+, "(\w+)"', text))
    assert used
    for name in used:
        assert icons.data_uri(name).startswith("data:image/svg+xml;base64,"), name


def test_css_places_nav_and_tab_icons():
    css = icons.css(("estrutura", "mapa"))
    assert 'data-key="0"' in css and 'data-key="1"' in css
    assert 'href="Temporal"' in css and 'href=""' in css


def test_no_emoji_left_in_interface_texts():
    for lang in ("pt", "en"):
        for key, text in json.loads((SRC / "locales" / f"{lang}.json").read_text("utf-8")).items():
            assert not EMOJI.search(text), (lang, key)
    for page in (SRC / "app").rglob("*.py"):
        assert not EMOJI.search(page.read_text(encoding="utf-8")), page.name
