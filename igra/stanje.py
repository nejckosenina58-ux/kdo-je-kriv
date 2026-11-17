"""Stanje ene igre: kateri primer se igra, kaj je igralec odkril, kaj je komu pokazal, zgodovina."""

import uuid

from .zgodba import privzeta_zgodba


class Igra:
    def __init__(self, zgodba: dict | None = None):
        """`zgodba` ima ključe primer, namigi, osumljenci (glej igra/zgodba.py).

        Brez nje se igra privzeti primer »Izginula ovojnica«.
        """
        zgodba = zgodba or privzeta_zgodba()
        self.id = uuid.uuid4().hex
        self.primer: dict = zgodba["primer"]
        self.namigi: dict[str, str] = zgodba["namigi"]
        self.osumljenci: dict[str, dict] = zgodba["osumljenci"]
        self.najdeni: list[str] = []                            # ID-ji namigov v beležki
        self.pokazani = {k: set() for k in self.osumljenci}     # kaj je kdo že videl
        self.zgodovina = {k: [] for k in self.osumljenci}       # sporočila za AI
        self.konec = False

    # --- skrivnosti ---------------------------------------------------------
    def odklenjene_skrivnosti(self, oseba: str) -> list[dict]:
        """Skrivnosti, za katere je igralec tej osebi pokazal VSE potrebne dokaze."""
        return [
            s for s in self.osumljenci[oseba]["skrivnosti"]
            if set(s["odklene"]) <= self.pokazani[oseba]
        ]

    def dovoljeni_namigi(self, oseba: str) -> set[str]:
        """Namigi, ki jih oseba v tem trenutku SME razkriti."""
        dovoljeni = set(self.osumljenci[oseba]["dejstva"])
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
        return [{"id": n, "besedilo": self.namigi[n]} for n in self.najdeni]

    # --- obtožba ------------------------------------------------------------
    def priznanje_krivca(self) -> str | None:
        """Namig, ki ga krivec razkrije, ko prizna (če ga ima)."""
        for s in self.osumljenci[self.primer["krivec"]]["skrivnosti"]:
            if s["nov_namig"]:
                return s["nov_namig"]
        return None

    def obtozi(self, oseba: str) -> dict:
        self.konec = True
        krivec = self.primer["krivec"]
        najdeni_kljucni = [n for n in self.primer["kljucni_namigi"] if n in self.najdeni]
        return {
            "pravilno": oseba == krivec,
            "krivec": self.osumljenci[krivec]["ime"],
            "razplet": self.primer["razplet"],
            "kljucnih_najdenih": len(najdeni_kljucni),
            "kljucnih_vseh": len(self.primer["kljucni_namigi"]),
            "priznanje": self.priznanje_krivca() in self.najdeni,
        }
