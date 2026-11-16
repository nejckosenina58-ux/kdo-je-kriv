"""Stanje ene igre: kaj je igralec odkril, kaj je komu pokazal, zgodovina pogovorov."""

import uuid

from .zgodba import NAMIGI, OSUMLJENCI, PRIMER


class Igra:
    def __init__(self):
        self.id = uuid.uuid4().hex
        self.najdeni: list[str] = []                       # ID-ji namigov v beležki
        self.pokazani = {k: set() for k in OSUMLJENCI}     # kaj je kdo že videl
        self.zgodovina = {k: [] for k in OSUMLJENCI}       # sporočila za AI
        self.konec = False

    # --- skrivnosti ---------------------------------------------------------
    def odklenjene_skrivnosti(self, oseba: str) -> list[dict]:
        """Skrivnosti, za katere je igralec tej osebi pokazal VSE potrebne dokaze."""
        return [
            s for s in OSUMLJENCI[oseba]["skrivnosti"]
            if set(s["odklene"]) <= self.pokazani[oseba]
        ]

    def dovoljeni_namigi(self, oseba: str) -> set[str]:
        """Namigi, ki jih oseba v tem trenutku SME razkriti."""
        dovoljeni = set(OSUMLJENCI[oseba]["dejstva"])
        for s in self.odklenjene_skrivnosti(oseba):
            if s["nov_namig"]:
                dovoljeni.add(s["nov_namig"])
        return dovoljeni

    # --- beležka ------------------------------------------------------------
    def dodaj_namige(self, oseba: str, predlagani: list[str]) -> list[str]:
        """Doda v beležko le namige, ki jih oseba res sme razkriti. Vrne nove."""
        novi = []
        for n in predlagani:
            if n in self.dovoljeni_namigi(oseba) and n not in self.najdeni:
                self.najdeni.append(n)
                novi.append(n)
        return novi

    def belezka(self) -> list[dict]:
        return [{"id": n, "besedilo": NAMIGI[n]} for n in self.najdeni]

    # --- obtožba ------------------------------------------------------------
    def obtozi(self, oseba: str) -> dict:
        self.konec = True
        pravilno = oseba == PRIMER["krivec"]
        najdeni_kljucni = [n for n in PRIMER["kljucni_namigi"] if n in self.najdeni]
        return {
            "pravilno": pravilno,
            "krivec": OSUMLJENCI[PRIMER["krivec"]]["ime"],
            "razplet": PRIMER["razplet"],
            "kljucnih_najdenih": len(najdeni_kljucni),
            "kljucnih_vseh": len(PRIMER["kljucni_namigi"]),
            "priznanje": "N9" in self.najdeni,
        }
