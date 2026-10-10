"""Chargement du jeu de données BNDE et nettoyage technique de base.

On reprend ici les étapes « techniques » de la partie 1 (doublons, format du taux).
Les corrections de fond (revenus négatifs, statuts incohérents...) ne sont PAS faites
ici : elles sont détectées et tracées par `controles.py`.
"""

from pathlib import Path

import pandas as pd

ORDRE_STATUTS = ["Bon", "Douteux", "Contentieux"]


def charger_donnees(chemin: str | Path) -> tuple[pd.DataFrame, int]:
    """Charge le CSV brut et renvoie (données dédoublonnées, nombre de doublons supprimés)."""
    df = pd.read_csv(chemin, sep=";", encoding="latin1")
    df = df.drop(columns=["Unnamed: 0"], errors="ignore")

    nb_doublons = int(df.duplicated().sum())
    df = df.drop_duplicates().reset_index(drop=True)

    # Taux stocké en texte avec une virgule décimale ("15,89") -> numérique
    df["Taux_Interet"] = pd.to_numeric(
        df["Taux_Interet"].astype(str).str.replace(",", ".", regex=False), errors="coerce"
    )

    # Garantie vide : on ne sait pas si c'est « pas de garantie » ou « non saisi ».
    # On garde l'information de manière explicite.
    df["Garantie"] = df["Garantie"].fillna("Non renseignée")

    df["Statut_Credit"] = pd.Categorical(df["Statut_Credit"], categories=ORDRE_STATUTS, ordered=True)
    return df, nb_doublons
