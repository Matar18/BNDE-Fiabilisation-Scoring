"""Estimation de la provision minimale réglementaire (Instruction BCEAO 026-11-2016, art. 16).

Calendrier minimal de dépréciation des créances douteuses (risques privés) :
- non couvertes par une garantie éligible : 20 % au transfert, 50 % trois mois après,
  100 % neuf mois après ;
- couvertes (garanties éligibles, hypothèque de 1er rang) : facultatif les deux premières
  années, 50 % à partir de la 3e année, 100 % à partir de la 4e année.

Hypothèses (le dataset ne contient ni encours, ni date de déclassement, ni valeur des garanties) :
- exposition = montant initial du crédit (majorant de l'encours restant dû) ;
- garantie éligible = « Immobilière » (hypothèque de 1er rang supposée), modifiable ;
- un crédit couvert l'est en totalité ;
- déclassement par impayé : transfert au 91e jour, donc jours depuis transfert = retard - 90 ;
- déclassement sans impayé > 90 j : date inconnue, on prend le transfert le plus récent
  possible (0 jour), ce qui donne la provision PLANCHER.
"""

import numpy as np
import pandas as pd

from .controles import SEUIL_IMPAYE_DOUTEUX_J, STATUTS_DECLASSES

GARANTIES_ELIGIBLES_DEFAUT = frozenset({"Immobilière"})


def taux_provision_minimal(couvert: bool, jours_depuis_transfert: float) -> float:
    j = max(float(jours_depuis_transfert), 0.0)
    if couvert:
        if j < 2 * 365:
            return 0.0
        if j < 3 * 365:
            return 0.5
        return 1.0
    if j < 90:
        return 0.2
    if j < 270:
        return 0.5
    return 1.0


def provision_minimale(df: pd.DataFrame, est_douteux: pd.Series,
                       garanties_eligibles=GARANTIES_ELIGIBLES_DEFAUT) -> pd.Series:
    """Provision minimale (FCFA) par crédit, 0 pour les créances saines."""
    couvert = df["Garantie"].isin(garanties_eligibles)
    jours = (df["Retard_Paiement_Jours"] - SEUIL_IMPAYE_DOUTEUX_J).clip(lower=0)
    taux = np.array([taux_provision_minimal(c, j) for c, j in zip(couvert, jours)])
    return pd.Series(np.where(est_douteux, taux * df["Montant_Credit"], 0.0), index=df.index)


def comparer_scenarios(df: pd.DataFrame, garanties_eligibles=GARANTIES_ELIGIBLES_DEFAUT) -> pd.DataFrame:
    """Compare trois façons de définir les créances douteuses."""
    scenarios = {
        "A. Statut déclaré": df["Statut_Credit"].astype(str).isin(STATUTS_DECLASSES),
        "B. Statut corrigé (A + déclassements obligatoires)": df["Statut_Corrige"].isin(STATUTS_DECLASSES),
        "C. Impayé > 90 j uniquement": df["Statut_Reglementaire_Impaye"] == "Douteux",
    }
    lignes = []
    for nom, masque in scenarios.items():
        prov = provision_minimale(df, masque, garanties_eligibles)
        lignes.append({
            "Scenario": nom,
            "Nb_credits_douteux": int(masque.sum()),
            "Taux_douteux_%": round(100 * masque.mean(), 1),
            "Montant_douteux_MFCFA": round(df.loc[masque, "Montant_Credit"].sum() / 1e6, 1),
            "Provision_min_MFCFA": round(prov.sum() / 1e6, 2),
        })
    return pd.DataFrame(lignes)
