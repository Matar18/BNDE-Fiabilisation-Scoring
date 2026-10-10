"""Règles de contrôle qualité du portefeuille de crédit.

Chaque règle est déclarée une seule fois (code, gravité, référence, action) et peut être
rejouée sur n'importe quel portefeuille ayant les mêmes colonnes.

Références réglementaires utilisées
-----------------------------------
- Instruction BCEAO n°026-11-2016 (engagements en souffrance, en vigueur depuis 2018) :
  * art. 4 : un impayé de 90 jours au plus reste une créance saine ;
  * art. 8 : au-delà de 90 jours d'impayé, la créance est douteuse (180 jours pour les
    États, les organismes publics et certains financements PME/PMI) ; une créance peut
    aussi être déclassée SANS impayé si un risque de non-recouvrement est probable ;
  * art. 9 : indices de ce risque (procédure collective, problèmes de gestion...).
- Taux d'usure bancaire UMOA : 15 % jusqu'au 31/05/2026, 14 % depuis le 01/06/2026
  (décision n°19 du Conseil des Ministres de l'UMOA du 29/12/2025). Il s'applique au
  taux effectif global (TEG), qui est toujours >= au taux nominal.
"""

from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

from .features import ajouter_variables_derivees

# --- Paramètres (modifiables) ------------------------------------------------
SEUIL_IMPAYE_DOUTEUX_J = 90          # art. 8, cas général
TAUX_USURE_BANQUES_PCT = 15.0        # 14.0 pour un crédit accordé depuis le 01/06/2026
SEUIL_ENDETTEMENT_ALERTE = 0.33      # pratique bancaire courante, PAS une règle BCEAO
COEF_TUKEY_EXTREME = 3.0             # valeurs « très éloignées » (Q3 + 3 x IQR)

GRAVITES = ["Critique", "Élevée", "Modérée", "Information"]
STATUTS_DECLASSES = ["Douteux", "Contentieux"]


def borne_haute_tukey(serie: pd.Series, k: float = COEF_TUKEY_EXTREME) -> float:
    q1, q3 = serie.quantile([0.25, 0.75])
    return q3 + k * (q3 - q1)


def statut_reglementaire(retard_jours, seuil: int = SEUIL_IMPAYE_DOUTEUX_J) -> np.ndarray:
    """Statut déduit UNIQUEMENT de l'impayé (critère objectif de l'art. 8-2°)."""
    return np.where(np.asarray(retard_jours) > seuil, "Douteux", "Sain")


@dataclass(frozen=True)
class Regle:
    code: str
    libelle: str
    gravite: str
    variable: str
    reference: str
    action: str
    detecter: Callable[[pd.DataFrame], pd.Series]


def _declasse(df):
    return df["Statut_Credit"].astype(str).isin(STATUTS_DECLASSES)


REGLES: list[Regle] = [
    Regle("R01", "Revenu négatif ou nul", "Critique", "Revenu_Mensuel",
          "Valeur impossible",
          "Retrouver le revenu dans le dossier. En attendant : mis à vide (pas de valeur absolue).",
          lambda d: d["Revenu_Mensuel"] <= 0),
    Regle("R02", f"Statut « Bon » avec impayé > {SEUIL_IMPAYE_DOUTEUX_J} jours", "Critique",
          "Retard_Paiement_Jours",
          "Instruction BCEAO 026-11-2016, art. 8 : déclassement obligatoire en douteux",
          "Déclasser en Douteux et constituer la provision.",
          lambda d: (d["Statut_Credit"].astype(str) == "Bon")
          & (d["Retard_Paiement_Jours"] > SEUIL_IMPAYE_DOUTEUX_J)),
    Regle("R03", "Montant de crédit extrême", "Élevée", "Montant_Credit",
          "Valeur très éloignée (Q3 + 3 x IQR)",
          "Vérifier le contrat (zéro en trop ?).",
          lambda d: d["Montant_Credit"] > borne_haute_tukey(d["Montant_Credit"])),
    Regle("R04", f"Taux > taux d'usure bancaire ({TAUX_USURE_BANQUES_PCT:g} %)", "Élevée", "Taux_Interet",
          "Loi sur l'usure UMOA (apprécié sur le TEG, toujours >= taux nominal)",
          "Vérifier le TEG et la date d'octroi. Si confirmé : crédit non conforme.",
          lambda d: d["Taux_Interet"] > TAUX_USURE_BANQUES_PCT),
    Regle("R05", "Mensualité supérieure au revenu", "Élevée", "Taux_Endettement",
          "Incohérence revenu / montant",
          "Vérifier revenu et montant : un tel crédit n'aurait pas dû être accordé.",
          lambda d: d["Taux_Endettement"] > 1),
    Regle("R06", "Revenu extrême", "Modérée", "Revenu_Mensuel",
          "Valeur très éloignée (Q3 + 3 x IQR)",
          "Vérifier la saisie (zéro en trop ?).",
          lambda d: d["Revenu_Mensuel"] > borne_haute_tukey(d.loc[d["Revenu_Mensuel"] > 0, "Revenu_Mensuel"])),
    Regle("R07", f"Taux d'endettement entre {SEUIL_ENDETTEMENT_ALERTE:.0%} et 100 %", "Modérée",
          "Taux_Endettement",
          "Pratique bancaire courante (~1/3 du revenu), hypothèse de travail",
          "Revoir la capacité de remboursement à l'octroi.",
          lambda d: d["Taux_Endettement"].between(SEUIL_ENDETTEMENT_ALERTE, 1, inclusive="right")),
    Regle("R08", f"Déclassé sans impayé > {SEUIL_IMPAYE_DOUTEUX_J} jours", "Modérée",
          "Retard_Paiement_Jours",
          "Instruction BCEAO 026-11-2016, art. 8-1° et 9 : possible si risque avéré, à justifier",
          "Documenter le motif (procédure collective, difficultés...) ou reclasser en sain.",
          lambda d: _declasse(d) & (d["Retard_Paiement_Jours"] <= SEUIL_IMPAYE_DOUTEUX_J)),
    Regle("R09", "Revenu manquant", "Information", "Revenu_Mensuel", "Donnée manquante",
          "Compléter depuis le dossier client.", lambda d: d["Revenu_Mensuel"].isna()),
    Regle("R10", "Taux d'intérêt manquant", "Information", "Taux_Interet", "Donnée manquante",
          "Compléter depuis le contrat.", lambda d: d["Taux_Interet"].isna()),
    Regle("R11", "Garantie non renseignée", "Information", "Garantie", "Donnée ambiguë",
          "Préciser : absence réelle de garantie ou oubli de saisie ?",
          lambda d: d["Garantie"] == "Non renseignée"),
    Regle("R12", "Âge manquant", "Information", "Age", "Donnée manquante",
          "Compléter depuis le dossier client.", lambda d: d["Age"].isna()),
]

# Anomalies qui rendent une ligne inutilisable pour entraîner un modèle
REGLES_HORS_PERIMETRE_MODELE = ["R01", "R02", "R03", "R06"]


def executer_controles(df: pd.DataFrame, regles: list[Regle] = REGLES) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Applique toutes les règles.

    Renvoie :
    - le portefeuille avec une colonne booléenne par règle + Nb_Anomalies + Gravite_Max ;
    - le rapport d'anomalies au format long (une ligne par client et par anomalie).
    """
    d = ajouter_variables_derivees(df)
    lignes = []
    for r in regles:
        masque = r.detecter(d).fillna(False).astype(bool)
        d[r.code] = masque
        for _, ligne in d.loc[masque].iterrows():
            lignes.append({
                "Client_ID": ligne["Client_ID"],
                "Code": r.code,
                "Anomalie": r.libelle,
                "Gravite": r.gravite,
                "Variable": r.variable,
                "Valeur": ligne[r.variable],
                "Statut_Credit": ligne["Statut_Credit"],
                "Reference": r.reference,
                "Action": r.action,
            })
    codes = [r.code for r in regles]
    d["Nb_Anomalies"] = d[codes].sum(axis=1)

    rang = {g: i for i, g in enumerate(GRAVITES)}
    gravite_par_code = {r.code: r.gravite for r in regles}

    def gravite_max(ligne):
        presentes = [gravite_par_code[c] for c in codes if ligne[c]]
        return min(presentes, key=rang.get) if presentes else "Aucune"

    d["Gravite_Max"] = d.apply(gravite_max, axis=1)

    rapport = pd.DataFrame(lignes)
    if not rapport.empty:
        rapport["Gravite"] = pd.Categorical(rapport["Gravite"], categories=GRAVITES, ordered=True)
        rapport = rapport.sort_values(["Gravite", "Code", "Client_ID"]).reset_index(drop=True)
    return d, rapport


def synthese_controles(portefeuille: pd.DataFrame, regles: list[Regle] = REGLES) -> pd.DataFrame:
    """Une ligne par règle : nombre de crédits, part du portefeuille, encours concerné."""
    n = len(portefeuille)
    lignes = []
    for r in regles:
        m = portefeuille[r.code]
        lignes.append({
            "Code": r.code,
            "Anomalie": r.libelle,
            "Gravite": r.gravite,
            "Nb_credits": int(m.sum()),
            "Part_portefeuille_%": round(100 * m.sum() / n, 1),
            "Montant_concerne_MFCFA": round(portefeuille.loc[m, "Montant_Credit"].sum() / 1e6, 1),
            "Reference": r.reference,
        })
    return pd.DataFrame(lignes)


def fiabiliser(portefeuille: pd.DataFrame) -> pd.DataFrame:
    """Construit la version « fiabilisée » du portefeuille (sans rien supprimer).

    - Revenu_Fiabilise : vide si le revenu est impossible (<= 0) ;
    - Statut_Corrige : « Bon » -> « Douteux » quand l'impayé dépasse 90 jours (art. 8) ;
    - Motif_Statut : pourquoi le crédit est dans ce statut ;
    - Hors_Perimetre_Modele : lignes à exclure de l'entraînement d'un score.
    """
    d = portefeuille.copy()
    d["Revenu_Fiabilise"] = d["Revenu_Mensuel"].where(d["Revenu_Mensuel"] > 0)

    statut = d["Statut_Credit"].astype(str)
    d["Statut_Reglementaire_Impaye"] = statut_reglementaire(d["Retard_Paiement_Jours"])
    d["Statut_Corrige"] = np.where(d["R02"], "Douteux", statut)

    d["Motif_Statut"] = np.select(
        [d["R02"], d["R08"], statut == "Bon"],
        ["Déclassement obligatoire (impayé > 90 j)", "Déclassé sans impayé > 90 j : motif à documenter",
         "Sain"],
        default="Déclassé avec impayé > 90 j",
    )
    d["Hors_Perimetre_Modele"] = d[REGLES_HORS_PERIMETRE_MODELE].any(axis=1)
    return d
