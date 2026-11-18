# -*- coding: utf-8 -*-
"""
branding.py
===========
Identidade visual do MangueTREE: textos institucionais, cores e logo (conceito
"raízes-circuito"). Fonte única usada por páginas e exportações.
"""

# --- Citation and repository (read by the About page) ---
from manguetree import __version__

REPO_URL = "https://github.com/luq317/MangueTREE"
CITATION = (f"Pereira LS, Motta LL, Matta TC, Chaves FO, Soares MLG (2026). MangueTREE v{__version__}. "
            f"{REPO_URL}")

# --- Textos institucionais ---
APP_NOME = "MangueTREE"
TAGLINE = "Análise estrutural de manguezais"
AUTOR = "Lucas Silva Pereira"
EMAIL = "pereira.lucas_1@posgraduacao.uerj.br"
LABORATORIO = "Núcleo de Estudos em Manguezais"
INSTITUICAO = "UERJ"
SITE = ""  # ainda sem endereço público
SELO_TEXTO = "MangueTREE"

# --- Cores da marca ---
VERDE_ESCURO = "#1F6B45"
VERDE = "#2E8B57"
VERDE_CLARO = "#57B77E"
MARROM = "#7B5230"
AZUL_DADOS = "#4C78A8"
TINTA = "#1A2B22"

# --- Logo (conceito B: copa cheia + raízes-circuito com nós de dados) ---
def logo_svg(size=48):
    return (
        f'<svg viewBox="0 0 64 64" width="{size}" height="{size}" '
        'xmlns="http://www.w3.org/2000/svg">'
        f'<circle cx="32" cy="18" r="12" fill="{VERDE_ESCURO}"/>'
        f'<circle cx="21" cy="23" r="8" fill="{VERDE}"/>'
        f'<circle cx="43" cy="23" r="8" fill="{VERDE}"/>'
        f'<circle cx="32" cy="12" r="6" fill="{VERDE_CLARO}"/>'
        f'<rect x="29" y="26" width="6" height="15" rx="2.5" fill="{MARROM}"/>'
        f'<path d="M32 41 V48 H21 V56" stroke="{VERDE}" stroke-width="2" fill="none"/>'
        f'<path d="M32 41 V45 H44 V56" stroke="{VERDE}" stroke-width="2" fill="none"/>'
        f'<path d="M32 44 V56" stroke="{VERDE}" stroke-width="2" fill="none"/>'
        f'<circle cx="21" cy="57" r="2.6" fill="{AZUL_DADOS}"/>'
        f'<circle cx="44" cy="57" r="2.6" fill="{AZUL_DADOS}"/>'
        f'<circle cx="32" cy="57" r="2.6" fill="{AZUL_DADOS}"/>'
        '</svg>'
    )

LOGO_SVG = logo_svg(48)


def desenhar_logo_mpl(ax):
    """Desenha o logo (conceito B) num eixo matplotlib com coordenadas 0..64."""
    import matplotlib.patches as mp
    ax.add_patch(mp.Circle((32, 46), 12, color=VERDE_ESCURO))
    ax.add_patch(mp.Circle((21, 41), 8, color=VERDE))
    ax.add_patch(mp.Circle((43, 41), 8, color=VERDE))
    ax.add_patch(mp.Circle((32, 52), 6, color=VERDE_CLARO))
    ax.add_patch(mp.FancyBboxPatch((29, 23), 6, 15, boxstyle="round,pad=0.4",
                                   color=MARROM, mutation_scale=1))
    # raízes-circuito (y invertido em relação ao SVG: base embaixo)
    ax.plot([32, 32, 21, 21], [23, 16, 16, 8], color=VERDE, lw=2, solid_capstyle="round")
    ax.plot([32, 32, 44, 44], [23, 19, 19, 8], color=VERDE, lw=2, solid_capstyle="round")
    ax.plot([32, 32], [20, 8], color=VERDE, lw=2, solid_capstyle="round")
    for x in (21, 32, 44):
        ax.add_patch(mp.Circle((x, 7), 2.6, color=AZUL_DADOS))
    ax.set_xlim(0, 64)
    ax.set_ylim(0, 64)
    ax.set_aspect("equal")
    ax.axis("off")
