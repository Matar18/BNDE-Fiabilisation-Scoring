"""Style graphique commun aux deux notebooks."""

import matplotlib.pyplot as plt

COULEURS_STATUT = {"Bon": "#0ca30c", "Douteux": "#fab219", "Contentieux": "#d03b3b"}
COULEURS_GRAVITE = {"Critique": "#d03b3b", "Élevée": "#ec835a", "Modérée": "#fab219", "Information": "#898781"}
BLEU, ORANGE, GRIS = "#2a78d6", "#eb6834", "#898781"
ENCRE, ENCRE_2, GRILLE, AXE = "#0b0b0b", "#52514e", "#e1e0d9", "#c3c2b7"


def appliquer_style():
    plt.rcParams.update({
        "figure.figsize": (10, 5),
        "figure.dpi": 110,
        "savefig.dpi": 150,
        "savefig.bbox": "tight",
        "figure.facecolor": "#fcfcfb",
        "axes.facecolor": "#fcfcfb",
        "axes.edgecolor": AXE,
        "axes.labelcolor": ENCRE_2,
        "axes.titlecolor": ENCRE,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.color": GRILLE,
        "grid.linewidth": 0.8,
        "xtick.color": ENCRE_2,
        "ytick.color": ENCRE_2,
        "legend.frameon": False,
        "font.family": "sans-serif",
    })
