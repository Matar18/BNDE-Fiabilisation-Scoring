"""Tests unitaires des règles de contrôle et du calcul de provision.

Lancer depuis la racine du projet :  python -m pytest -q
"""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.chargement import charger_donnees
from src.controles import executer_controles, fiabiliser, statut_reglementaire
from src.features import mensualite
from src.provisions import taux_provision_minimal

DATA = Path(__file__).resolve().parents[1] / "data" / "dataset_BNDE.csv"


def test_mensualite_formule_annuite():
    # 1 200 000 FCFA à 12 % sur 12 mois -> 106 618,55 FCFA (formule d'annuité)
    assert mensualite(1_200_000, 12, 12) == pytest.approx(106_618.55, abs=0.01)


def test_mensualite_taux_nul():
    assert mensualite(1_200_000, 0, 12) == pytest.approx(100_000)


def test_seuil_90_jours():
    # Art. 4 et 8 : 90 jours = encore sain, 91 jours = douteux
    assert list(statut_reglementaire([0, 90, 91, 980])) == ["Sain", "Sain", "Douteux", "Douteux"]


@pytest.mark.parametrize("couvert, jours, attendu", [
    (False, 0, 0.2), (False, 89, 0.2), (False, 90, 0.5), (False, 270, 1.0),
    (True, 0, 0.0), (True, 729, 0.0), (True, 730, 0.5), (True, 1095, 1.0),
])
def test_calendrier_provision(couvert, jours, attendu):
    assert taux_provision_minimal(couvert, jours) == attendu


def test_controles_sur_dataset_reel():
    df, nb_doublons = charger_donnees(DATA)
    assert nb_doublons == 3 and len(df) == 500

    portefeuille, rapport = executer_controles(df)
    critiques = set(rapport.loc[rapport["Code"] == "R02", "Client_ID"])
    assert critiques == {"CLI0088", "CLI0304"}           # « Bon » avec impayé > 90 j
    assert "CLI0043" in set(rapport.loc[rapport["Code"] == "R03", "Client_ID"])  # 95 M FCFA

    f = fiabiliser(portefeuille)
    assert (f.loc[f["Client_ID"] == "CLI0088", "Statut_Corrige"] == "Douteux").all()
    assert f["Revenu_Fiabilise"].min() > 0               # plus aucun revenu impossible
    assert len(f) == len(df)                              # rien n'est supprimé
