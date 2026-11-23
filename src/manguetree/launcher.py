# -*- coding: utf-8 -*-
# MangueTREE: structural analysis of mangrove forest plots.
# Copyright (c) 2026 The MangueTREE authors (see README.md and CITATION.cff).
#
# This program is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the GNU General Public License for more details.
# You should have received a copy of the GNU General Public License along with this
# program. If not, see <https://www.gnu.org/licenses/>.
"""
launcher.py
===========
Entry point of MangueTREE as a DESKTOP APPLICATION.

Starts the Streamlit server on localhost and opens the default browser. It works
both from Python and packaged with PyInstaller (the frozen mode is detected through
sys.frozen / sys._MEIPASS). It sets MANGUETREE_DESKTOP=1, which makes the app show
the "Quit MangueTREE" button (the packaged builds have no console window to close).

Direct use (development):
    python -m manguetree.launcher
"""
import os
import sys
import pathlib


def _suprimir_prompt_email():
    """Avoid the Streamlit e-mail prompt on the first run (creates credentials.toml)."""
    try:
        cfg = pathlib.Path.home() / ".streamlit"
        cfg.mkdir(parents=True, exist_ok=True)
        cred = cfg / "credentials.toml"
        if not cred.exists():
            cred.write_text('[general]\nemail = ""\n', encoding="utf-8")
    except Exception:
        pass


def base_dir():
    """Directory of the manguetree package (also in the packaged mode)."""
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, "manguetree")  # PyInstaller extraction folder
    return os.path.dirname(os.path.abspath(__file__))


def app_dir():
    """App folder (holds Home.py, pages/ and .streamlit/config.toml)."""
    return os.path.join(base_dir(), "app")


def build_argv():
    """Arguments of `streamlit run` for the packaged app."""
    return [
        "streamlit", "run", os.path.join(app_dir(), "Home.py"),
        "--server.port=8501",
        "--server.address=localhost",
        "--server.headless=false",
        "--browser.gatherUsageStats=false",
        "--global.developmentMode=false",
    ]


def main():
    base = base_dir()
    # Root that holds the "manguetree" package (src/ in development, _MEIPASS when frozen)
    sys.path.insert(0, os.path.dirname(base))
    # Streamlit reads .streamlit/config.toml from the working directory: use the app's
    os.chdir(app_dir())
    _suprimir_prompt_email()

    # Desktop mode (shows the quit button); no telemetry or development mode; the
    # browser opens by itself (headless=false)
    os.environ["MANGUETREE_DESKTOP"] = "1"
    os.environ.setdefault("STREAMLIT_BROWSER_GATHER_USAGE_STATS", "false")
    os.environ.setdefault("STREAMLIT_GLOBAL_DEVELOPMENT_MODE", "false")
    os.environ.setdefault("STREAMLIT_SERVER_HEADLESS", "false")

    sys.argv = build_argv()
    from streamlit.web import cli as stcli
    sys.exit(stcli.main())


if __name__ == "__main__":
    main()
