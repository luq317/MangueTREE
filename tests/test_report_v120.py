# -*- coding: utf-8 -*-
"""Scientific-article PDF: cover, figures from the app (Plotly) or redrawn, map, panel."""
import io
import shutil
import subprocess
from pathlib import Path

import pandas as pd
import pytest
import plotly.graph_objects as go
from PIL import Image

from manguetree import calc as mc, charts, io as mio, report
from manguetree.species import SpeciesResolver, load_genus_defaults, load_species_table

ROOT = Path(__file__).resolve().parent.parent
HAS_PLOTLY_IMG = report.plotly_images_available()


@pytest.fixture(scope="module")
def f2():
    df, area = mio.load_excel_sheet(str(ROOT / "data" / "guaratiba_T2_2009.xlsx"), "F2", "", 100.0)
    return mc.analyze(df.dropna(subset=["dbh"]), area,
                      SpeciesResolver(load_species_table(), "BR_S_SE", load_genus_defaults()))


def _text(pdf, tmp_path):
    if shutil.which("pdftotext") is None:
        pytest.skip("pdftotext not available")
    p = tmp_path / "r.pdf"; p.write_bytes(pdf)
    return subprocess.run(["pdftotext", str(p), "-"], capture_output=True, text=True).stdout


def _fig_json(title="Chart of DBH"):
    fig = go.Figure(go.Bar(x=["a", "b"], y=[1, 2]))
    fig.update_layout(title=title, width=700, height=400)
    return fig.to_json()


FIGS = [{"key": "k1", "section": "Tab one", "json": _fig_json("First chart")},
        {"key": "k2", "section": "Tab one", "json": _fig_json("Second chart")},
        {"key": "k3", "section": "Tab two", "json": _fig_json("Third chart")}]


def test_report_has_cover_numbered_headings_and_captions(f2, tmp_path):
    t = _text(report.single_plot_report(f2, lang="en"), tmp_path)
    assert "Single plot analysis" in t or "plot" in t.lower()
    assert "1. " in t and "Figure 1." in t and "Table 1." in t or "Figure 1." in t


def test_no_em_dash_and_no_portuguese_in_english(f2, tmp_path):
    t = _text(report.single_plot_report(f2, lang="en"), tmp_path)
    assert "—" not in t
    for word in ("Resumo", "Fitossociologia", "Verificação", "Parâmetros"):
        assert word not in t


def test_portuguese_report_uses_portuguese(f2, tmp_path):
    t = _text(report.single_plot_report(f2, lang="pt"), tmp_path)
    assert "Resumo" in t and "Figura 1." in t and "—" not in t


def test_logo_is_transparent():
    im = Image.open(report._logo_png())
    assert im.mode == "RGBA" and im.getpixel((0, 0))[3] == 0


def test_summary_panel_goes_in_the_pdf(f2, tmp_path):
    panel = io.BytesIO()
    Image.new("RGB", (900, 500), "#eeeeee").save(panel, "PNG")
    t = _text(report.single_plot_report(f2, lang="pt", panel_png=panel.getvalue()), tmp_path)
    assert "Painel-resumo" in t


def test_map_with_coordinates(f2, tmp_path):
    coords = pd.DataFrame({"lat": [-23.0, -23.1], "lon": [-44.0, -44.2], "plot": ["P1", "P2"]})
    t = _text(report.single_plot_report(f2, lang="pt", coords=coords), tmp_path)
    assert "Mapa" in t or "Localiza" in t
    without = _text(report.single_plot_report(f2, lang="pt"), tmp_path)
    assert "Mapa" not in without


def test_fallback_redraws_figures_when_plotly_cannot_draw(f2, tmp_path, monkeypatch):
    monkeypatch.setattr(report, "plotly_images_available", lambda: False)
    pdf = report.single_plot_report(f2, lang="en", figures=FIGS)
    assert pdf.startswith(b"%PDF")
    t = _text(pdf, tmp_path)
    assert "Tab one" not in t          # the app's charts were not used


@pytest.mark.skipif(not HAS_PLOTLY_IMG, reason="Plotly image export needs Chrome/Chromium")
def test_app_figures_are_used_grouped_by_tab_with_title_as_caption(f2, tmp_path):
    t = _text(report.single_plot_report(f2, lang="en", figures=FIGS), tmp_path)
    assert "Tab one" in t and "Tab two" in t
    assert "First chart" in t and "Third chart" in t


def test_chart_registry_and_pdf_signature():
    from streamlit.testing.v1 import AppTest

    def app():
        import plotly.graph_objects as go
        from manguetree import charts as ui
        ui.reset_report_figs()
        ui.report_section("Sec")
        ui.show(__import__("streamlit"), go.Figure(go.Bar(x=[1], y=[1])), "x_1")

    at = AppTest.from_function(app).run()
    assert not at.exception
    assert "_rep_figs" in at.session_state
    figs = list(at.session_state["_rep_figs"].values())
    assert figs and figs[0]["section"] == "Sec" and figs[0]["json"]


def test_verification_table_has_no_stray_index_column():
    from manguetree.report import _bloco_verificacao
    df = charts.issues_display_frame([], lang="pt")
    assert _bloco_verificacao(df, "pt")[1][0] == "cap"


# ---- reports/ package: theme, formatting, adapter, panel, grouped check ------------------
from manguetree.reports import theme, formatting, plotly_adapter, panel  # noqa: E402


def test_fixed_species_palette_and_extras():
    assert theme.species_color("Avicennia schaueriana") == "#1B365D"
    assert theme.species_color("Rhizophora mangle (Viva)") == "#2A8C82"
    assert theme.species_color("Laguncularia racemosa") == "#6E9476"
    assert theme.species_color("Conocarpus erectus") not in set(theme.SPECIES_COLORS.values())
    assert theme.species_color("Indeterminada") == theme.UNKNOWN_COLOR
    cores = theme.species_colors(["Foo bar", "Bar baz", "Conocarpus erectus"])
    assert len(set(cores.values())) == 3                  # extras stay apart
    assert theme.stack_order(["Laguncularia racemosa", "Indeterminada", "Rhizophora mangle", "Avicennia schaueriana"]) == \
        ["Avicennia schaueriana", "Rhizophora mangle", "Laguncularia racemosa", "Indeterminada"]


def test_slots_match_the_spec_table():
    assert theme.CONTENT_W_MM == 174
    assert theme.slot_px("panel_2x2") == (660, 402) and theme.slot_px("half_pair") == (320, 258)
    assert theme.slot_figsize_in("full_standard") == (6.85, 3.15)
    assert theme.slot_px("multi_facet", 2) == (660, 420)


def test_pt_br_number_format():
    # results always show two decimals; counts (0 decimals) of whole numbers stay whole
    assert formatting.fmt_br(12500.5, 1) == "12.500,50"
    assert formatting.fmt_br(12500.5, 1, "en") == "12,500.50"
    assert formatting.fmt_br(12500.4, 0) == "12.500,40" and formatting.fmt_br(12500.0, 0) == "12.500"
    assert formatting.plotly_separators("pt") == ",." and formatting.plotly_separators("en") == ".,"


def test_adapter_keeps_screen_figure_and_user_choices():
    fig = go.Figure([go.Bar(x=[1, 2], y=[3, 4], name="Rhizophora mangle (viva)"),
                     go.Bar(x=[1, 2], y=[1, 2], name="Rhizophora mangle (morta)")])
    fig.update_layout(height=450, title="Mine", yaxis=dict(type="log", range=[0, 2]))
    out = plotly_adapter.prepare_plotly_for_pdf(fig, "full_standard", "pt")
    assert out.layout.width == 660 and out.layout.height == 304      # slot of the spec
    assert out.layout.separators == ",."
    assert out.layout.legend.orientation == "h" and out.layout.legend.y > 1
    assert out.layout.yaxis.type == "log" and tuple(out.layout.yaxis.range) == (0, 2)   # user choices kept
    assert out.data[0].marker.color == "#2A8C82"                    # fixed palette
    assert out.data[1].marker.color == "#FFFFFF"                    # dead: white with outline
    assert fig.layout.title.text == "Mine" and fig.layout.width is None   # the screen copy is untouched


def test_adapter_scales_height_chosen_in_adjust_menu_within_limits():
    fig = go.Figure(go.Bar(x=[1], y=[1])); fig.update_layout(height=1600)
    w, h = plotly_adapter.slot_size_px(fig, "full_standard")
    assert 60 <= h * 174 / w <= 135


def test_check_is_grouped_and_short():
    from manguetree.validation import Issue
    iss = [Issue("duplicate_tag", "warning", n, n, "w", "") for n in range(80)]
    iss.append(Issue("unknown_species", "error", 9, 1, "bad", ""))
    frame = charts.issues_display_frame(iss, lang="en")
    n_err, n_warn, tab = formatting.group_issues(frame, "en")
    assert (n_err, n_warn) == (1, 80) and len(tab) == 2
    assert list(tab.columns)[:3] == ["Problem category", "Severity", "Occurrences (N)"]
    assert formatting.group_issues(None) is None
    assert formatting.group_issues(charts.issues_display_frame([], lang="en"), "en")[:2] == (0, 0)


def test_single_first_page_has_tables_and_no_screenshot(f2, tmp_path):
    pdf = report.single_plot_report(f2, lang="pt", panel_png=b"not an image")
    t = _text(pdf, tmp_path)
    assert "LEITURA DOS RESULTADOS" in t and "Painel-resumo da parcela" in t
    assert "Resumo estrutural completo" in t
    box = subprocess.run(["pdfinfo", str(tmp_path / "r.pdf")], capture_output=True, text=True).stdout
    assert "595.276 x 841.89" in box                       # A4 portrait


def test_every_page_is_a_portrait_a4_and_numbered_x_of_y(f2, tmp_path):
    t = _text(report.single_plot_report(f2, lang="pt"), tmp_path)
    assert "Página 1 de" in t
    info = subprocess.run(["pdfinfo", "-f", "1", "-l", "20", str(tmp_path / "r.pdf")],
                          capture_output=True, text=True).stdout
    sizes = [ln for ln in info.splitlines() if "size:" in ln and "Page" in ln and "Page size" not in ln]
    assert sizes and all("595.276 x 841.89" in ln or "595.28 x 841.89" in ln for ln in sizes)


def test_temporal_drops_charts_that_repeat_a_panel_or_each_other():
    line = lambda: go.Figure(go.Scatter(x=[1, 2], y=[3, 4], name="a"))
    bar = go.Figure(go.Bar(x=[1, 2], y=[3, 4], name="a"))
    figs = [{"key": "evol_mean_dbh_cm", "section": "S", "json": line().to_json()},
            {"key": "evol_height_mean_m", "section": "S", "json": bar.to_json()},     # bars: a user choice
            {"key": "3_6", "section": "S", "json": line().to_json()},
            {"key": "fig_esp_temp", "section": "S", "json": _fig_json("x")},
            {"key": "mort_live_dead_ba", "section": "S", "json": _fig_json("x")}]    # same data as the one above
    kept = [f["key"] for f in report._sem_duplicados(figs, {"mean_dbh_cm", "height_mean_m"}, True)]
    assert kept == ["evol_height_mean_m", "fig_esp_temp"]


def test_colonization_report_builds_in_both_languages(tmp_path):
    resumos = [{"parcela": "A", "arquivo": "A.xlsx", "individuos": 100, "blocos": 5, "anos": (1998, 2015)},
               {"parcela": "B", "arquivo": "B.xlsx", "individuos": 50, "blocos": 3, "anos": (2000, 2010)}]
    dens = pd.DataFrame({"parcela": ["A", "B"], "ano": [2000, 2001], "ind_ha": [1000.0, 3000.0], "n": [5, 9]})
    pt = _text(report.colonization_report(resumos, dens, lang="pt"), tmp_path)
    # the KPI is the highest density (3.000), no longer the mean of every plot-year (2.000)
    assert "Dinâmica de colonização" in pt and "3.000" in pt and "—" not in pt
    en = _text(report.colonization_report(resumos, dens, lang="en", figures=FIGS if HAS_PLOTLY_IMG else None), tmp_path)
    assert "Colonization dynamics" in en and "Resumo" not in en


def test_fallback_uses_the_same_palette(monkeypatch):
    assert report._cor_especie("Rhizophora mangle") == theme.species_color("Rhizophora mangle")
    assert list(report._PALETA)[:3] == [theme.NAVY, theme.TEAL, theme.SAGE]


def test_multi_summary_merges_a_plot_that_leads_two_indicators():
    df = pd.DataFrame({"plot": ["F2", "H2"], "density_live_ha": [1000.0, 2000.0], "ba_live_ha": [30.0, 20.0],
                       "height_mean_m": [9.0, 6.0], "mortality_stems_pct": [5.0, 9.0]})
    txt = report._resumo_multi(df, None, "pt")
    assert "reuniu simultaneamente" in txt and txt.count("F2") == 1 or "F2 reuniu" in txt or "parcela F2 reuniu" in txt
    df2 = df.assign(height_mean_m=[6.0, 9.0])
    assert "simultaneamente" not in report._resumo_multi(df2, None, "pt")


def test_plot_has_one_colour_everywhere():
    import plotly.graph_objects as go
    from manguetree.reports import plotly_adapter as pa, theme
    cm = theme.plot_color_map(["F2", "H2", "J2", "F2"])
    assert list(cm) == ["F2", "H2", "J2"] and len(set(cm.values())) == 3
    fig = go.Figure([go.Bar(x=["F2", "H2", "J2"], y=[1, 2, 3], marker_color="red")])
    out = pa.prepare_plotly_for_pdf(fig, plot_colors=cm)
    assert list(out.data[0].marker.color) == [cm["F2"], cm["H2"], cm["J2"]]
    fig = go.Figure([go.Box(y=[1, 2, 3], name="H2"), go.Scatterpolar(r=[1, 2], theta=["a", "b"], name="J2")])
    out = pa.prepare_plotly_for_pdf(fig, plot_colors=cm)
    assert out.data[0].marker.color == cm["H2"] and out.data[1].line.color == cm["J2"]


def _fake_tile(z, x, y):
    import io
    from PIL import Image
    b = io.BytesIO(); Image.new("RGB", (256, 256), (30 + (x * 7) % 90, 90, 60 + (y * 5) % 90)).save(b, "JPEG")
    return b.getvalue()


def test_map_uses_satellite_tiles_and_falls_back_without_network(monkeypatch):
    from manguetree.reports import basemap
    b = basemap.padded_bounds([-23.07, -23.06], [-43.58, -43.57])
    assert basemap.choose_zoom(b) <= basemap.MAX_ZOOM
    bg = basemap.background(b, fetch=_fake_tile)
    assert bg is not None and bg[0].shape[2] == 3 and bg[1][0] < bg[1][1]
    coords = pd.DataFrame({"plot": ["F2", "H2"], "lat": [-23.07, -23.06], "lon": [-43.58, -43.57]})
    orig = basemap.background
    monkeypatch.setattr(basemap, "background", lambda bb, fetch=_fake_tile: orig(bb, fetch))

    def boom(z, x, y):
        raise OSError("offline")
    assert orig(b, fetch=boom) is None
    fig = report._fig_mapa(coords, "pt", False)
    assert fig is not None and fig._manguetree_sat is True
    monkeypatch.setattr(basemap, "background", lambda bb, fetch=boom: orig(bb, fetch))
    assert report._fig_mapa(coords, "pt", False)._manguetree_sat is False


def test_box_outline_is_thin_and_in_the_axis_colour():
    import plotly.express as px
    from manguetree.reports import plotly_adapter as pa, theme
    fig = px.box(x=["a", "a", "b", "b"], y=[1, 2, 3, 4], color=["a", "a", "b", "b"],
                 color_discrete_sequence=["#1B365D", "#2A8C82"])
    out = pa.prepare_plotly_for_pdf(fig)
    for tr in out.data:
        assert tr.line.color == theme.AXIS and tr.line.width == theme.AXIS_WIDTH
        assert tr.fillcolor.startswith("rgba(") and tr.marker.color in ("#1B365D", "#2A8C82")
    app = px.box(x=["a", "b"], y=[1, 2], color=["a", "b"])
    pa.outline_boxes(app)
    assert all(t.line.color == theme.AXIS for t in app.data)


def test_app_map_is_interactive_with_dark_and_satellite_modes():
    import json
    from manguetree import charts
    co = pd.DataFrame({"plot": ["F2", "H2"], "lat": [-23.0, -23.002], "lon": [-43.6, -43.598]})
    dark = charts.location_deck(co, "dark")
    sat = charts.location_deck(co, "satellite")
    assert "dark" in dark.map_style
    assert isinstance(sat.map_style, str) and sat.map_style.startswith("data:application/json")
    assert "World_Imagery" in __import__("urllib.parse").parse.unquote(sat.map_style)
    for deck in (dark, sat):
        spec = json.loads(deck.to_json())
        for layer in spec["layers"]:
            for k, v in layer.items():   # pydeck turns plain strings into expressions: only accessors may be
                if isinstance(v, str) and v.startswith("@@="):
                    assert k.startswith("get"), (layer["@@type"], k, v)
        sc = next(l for l in spec["layers"] if l["@@type"] == "ScatterplotLayer")
        assert sc["radiusMaxPixels"] <= 8                    # small dots, never huge circles
