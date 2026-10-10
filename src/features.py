"""Variables dérivées : mensualité, taux d'endettement, ratio montant / revenu."""

import numpy as np
import pandas as pd


def mensualite(montant, taux_annuel_pct, duree_mois):
    """Mensualité d'un prêt amortissable à échéances constantes.

    M = P * r / (1 - (1 + r) ** -n), avec r = taux annuel / 12.
    Fonctionne sur des scalaires ou des Series pandas. Renvoie NaN si le taux est manquant.
    """
    r = np.asarray(taux_annuel_pct, dtype=float) / 100 / 12
    p = np.asarray(montant, dtype=float)
    n = np.asarray(duree_mois, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        m = np.where(r == 0, p / n, p * r / (1 - (1 + r) ** -n))
    if isinstance(montant, pd.Series):
        return pd.Series(m, index=montant.index, name="Mensualite")
    return m


def ajouter_variables_derivees(df: pd.DataFrame, col_revenu: str = "Revenu_Mensuel") -> pd.DataFrame:
    """Ajoute Mensualite, Taux_Endettement et Montant_sur_Revenu_Annuel.

    Le taux d'endettement n'est calculé que si le revenu est strictement positif
    (un revenu nul ou négatif est une anomalie, pas une information).
    """
    df = df.copy()
    df["Mensualite"] = mensualite(df["Montant_Credit"], df["Taux_Interet"], df["Duree_Mois"])
    revenu_valide = df[col_revenu].where(df[col_revenu] > 0)
    df["Taux_Endettement"] = df["Mensualite"] / revenu_valide
    df["Montant_sur_Revenu_Annuel"] = df["Montant_Credit"] / (12 * revenu_valide)
    return df
