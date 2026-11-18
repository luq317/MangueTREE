def test_version():
    import manguetree

    assert manguetree.__version__ == "1.1.0"


def test_launcher_imports():
    import manguetree.launcher  # noqa: F401


def test_launcher_uses_app_dir_with_streamlit_config():
    import tomllib
    from pathlib import Path

    from manguetree import launcher

    app = Path(launcher.app_dir())
    cfg = app / ".streamlit" / "config.toml"
    assert cfg.is_file()
    assert tomllib.loads(cfg.read_text(encoding="utf-8"))["theme"]["primaryColor"]
    # the entry script streamlit is told to run lives in that same dir
    argv = launcher.build_argv()
    assert Path(argv[2]) == app / "Home.py" and Path(argv[2]).is_file()


def test_root_config_matches_packaged_config():
    from pathlib import Path

    from manguetree import launcher

    root = Path(__file__).resolve().parents[1] / ".streamlit" / "config.toml"
    packaged = Path(launcher.app_dir()) / ".streamlit" / "config.toml"
    assert root.read_bytes() == packaged.read_bytes()
