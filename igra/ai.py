"""Povezava z AI. Vsaka napaka se pretvori v AINapaka s prijaznim sporočilom za igralca."""

import json
import os
import random
import re

from .prompti import sestavi_navodila
from .stanje import Igra
from .zgodba import OSUMLJENCI


class AINapaka(Exception):
    """Napaka, ki jo lahko brez skrbi pokažemo igralcu."""


SHEMA_ODGOVORA = {
    "type": "object",
    "properties": {
        "odgovor": {"type": "string"},
        "razkriti_namigi": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["odgovor", "razkriti_namigi"],
    "additionalProperties": False,
}

# Modeli, ki podpirajo samodejni nadomestni model ob zavrnitvi (server-side fallback).
MODELI_Z_NADOMESTNIM = {"claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5",
                        "claude-fable-5-2", "claude-fable-5-1"}

# --- zaščita osebnih podatkov ------------------------------------------------
_VZORCI_OSEBNIH = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "[e-pošta odstranjena]"),
    (re.compile(r"\b\d{13}\b"), "[številka odstranjena]"),               # EMŠO
    (re.compile(r"(\+?386|0)[\s/-]?\d{2}[\s/-]?\d{3}[\s/-]?\d{3}\b"), "[telefon odstranjen]"),
]


def odstrani_osebne_podatke(besedilo: str) -> str:
    for vzorec, zamenjava in _VZORCI_OSEBNIH:
        besedilo = vzorec.sub(zamenjava, besedilo)
    return besedilo


# --- izbira načina --------------------------------------------------------------
def nacin() -> str:
    """Vrne "anthropic" (pravi AI) ali "demo".

    AI_PONUDNIK=auto (privzeto): pravi AI, če je nastavljen ANTHROPIC_API_KEY, sicer demo.
    AI_PONUDNIK=anthropic: vedno pravi AI (brez ključa igralec dobi jasno napako).
    AI_PONUDNIK=demo: vedno demo.
    """
    ponudnik = os.getenv("AI_PONUDNIK", "auto").strip().lower()
    if ponudnik == "demo":
        return "demo"
    if ponudnik == "auto" and not _ima_kljuc():
        return "demo"
    return "anthropic"


def _ima_kljuc() -> bool:
    kljuc = os.getenv("ANTHROPIC_API_KEY", "").strip()
    return bool(kljuc) and kljuc != "vas-kljuc-tukaj"


# --- glavni vstop --------------------------------------------------------------
def odgovori(igra: Igra, oseba: str, sporocilo: str) -> tuple[str, list[str]]:
    """Vrne (besedilo odgovora, seznam novo najdenih namigov)."""
    sporocilo = odstrani_osebne_podatke(sporocilo.strip())[:500]
    if not sporocilo:
        raise AINapaka("Vprašanje je prazno. Napišite, kaj želite vprašati.")

    if nacin() == "demo":
        besedilo, predlagani = _demo(igra, oseba, sporocilo)
    else:
        besedilo, predlagani = _anthropic(igra, oseba, sporocilo)

    # Zgodovino posodobimo šele, ko je odgovor uspešen.
    igra.zgodovina[oseba].append({"role": "user", "content": sporocilo})
    igra.zgodovina[oseba].append({"role": "assistant", "content": besedilo})
    novi = igra.dodaj_namige(oseba, predlagani)   # koda preveri, ali je namig dovoljen
    return besedilo, novi


# --- Anthropic Claude -----------------------------------------------------------
_odjemalec = None


def _dobi_odjemalca():
    global _odjemalec
    if _odjemalec is None:
        import anthropic
        if not _ima_kljuc():
            raise AINapaka("AI ni nastavljen (manjka ključ v datoteki .env). "
                           "Prosite skrbnika ali zaženite igro v načinu »demo«.")
        _odjemalec = anthropic.Anthropic(
            timeout=float(os.getenv("AI_CASOVNA_OMEJITEV", "30")),
            max_retries=1,
        )
    return _odjemalec


def _anthropic(igra: Igra, oseba: str, sporocilo: str) -> tuple[str, list[str]]:
    import anthropic

    model = os.getenv("AI_MODEL", "claude-opus-5-5")
    ime = OSUMLJENCI[oseba]["ime"]
    parametri = dict(
        model=model,
        max_tokens=4000,
        system=sestavi_navodila(igra, oseba),
        messages=igra.zgodovina[oseba] + [{"role": "user", "content": sporocilo}],
        output_config={
            "effort": "low",   # kratki pogovorni odgovori -> hitreje in ceneje
            "format": {"type": "json_schema", "schema": SHEMA_ODGOVORA},
        },
    )

    try:
        odjemalec = _dobi_odjemalca()
        if model in MODELI_Z_NADOMESTNIM and os.getenv("AI_NADOMESTNI_MODEL", "1") == "1":
            odziv = odjemalec.beta.messages.create(
                betas=["server-side-fallback-2026-07-01"], fallbacks="default", **parametri)
        else:
            odziv = odjemalec.messages.create(**parametri)
    except AINapaka:
        raise
    except anthropic.APITimeoutError:
        raise AINapaka(f"{ime} predolgo razmišlja (AI se ni odzval pravočasno). Poskusite znova.")
    except anthropic.APIConnectionError:
        raise AINapaka("Ni povezave z AI storitvijo. Preverite internetno povezavo in poskusite znova.")
    except anthropic.AuthenticationError:
        raise AINapaka("Ključ za AI ni veljaven. Obvestite skrbnika igre.")
    except anthropic.RateLimitError:
        raise AINapaka("Preveč vprašanj naenkrat. Počakajte pol minute in poskusite znova.")
    except anthropic.APIStatusError as e:
        raise AINapaka(f"AI storitev trenutno ne deluje (napaka {e.status_code}). Poskusite čez nekaj minut.")

    if odziv.stop_reason == "refusal":
        raise AINapaka(f"{ime} na to vprašanje noče odgovoriti. Poskusite ga vprašati drugače.")

    if odziv.stop_reason == "max_tokens":
        raise AINapaka(f"{ime} se je zapletel v predolg odgovor. Poskusite s krajšim vprašanjem.")

    surovo = next((b.text for b in odziv.content if b.type == "text"), "").strip()
    if not surovo:
        raise AINapaka(f"{ime} je samo molče skomignil z rameni (prazen odgovor AI). Poskusite znova.")

    try:
        podatki = json.loads(surovo)
        besedilo = str(podatki.get("odgovor", "")).strip()
        namigi = [str(n) for n in podatki.get("razkriti_namigi", [])]
    except (json.JSONDecodeError, AttributeError):
        besedilo, namigi = surovo, []        # neveljaven JSON: pokažemo besedilo, brez namigov

    if not besedilo:
        raise AINapaka(f"{ime} ne ve, kaj bi rekel. Poskusite z drugim vprašanjem.")
    return besedilo, namigi


# --- način brez AI (za testiranje in predstavitve brez interneta) ---------------
# Demo ni pravi AI: odgovor sestavi iz podatkov o osebi. Da ni vedno enak,
# izbere dejstvo, ki se najbolj ujema z vprašanjem, in naključen uvod.
_UVODI = {
    "bojan": ["Ah, spet vprašanja …", "Poslušajte, jaz delam, ne čvekam.", "No, če ravno hočete vedet' …"],
    "mojca": ["Če dovolite, bom natančna.", "To je pravzaprav preprosto.", "Upam, da me ne sumničite."],
    "tim": ["Ej, čakte …", "Okej, okej, ni panike …", "Res nisem nič naredil, ampak …"],
    "vesna": ["Oh, kar sedite.", "Saj vam rada pomagam.", "Hm, naj pomislim …"],
}
_IZMIKI = [
    "Na to res ne vem, kaj bi rekel.",
    "Tega ne vem. Vprašajte raje kaj drugega.",
    "O tem nimam kaj povedati.",
]


def _besede(besedilo: str) -> set[str]:
    return {b[:5] for b in re.findall(r"\w+", besedilo.lower()) if len(b) > 3}


def _demo(igra: Igra, oseba: str, sporocilo: str = "") -> tuple[str, list[str]]:
    o = OSUMLJENCI[oseba]
    uvod = random.choice(_UVODI.get(oseba, ["Hm."]))

    for s in igra.odklenjene_skrivnosti(oseba):
        if s["nov_namig"] and s["nov_namig"] not in igra.najdeni:
            return f"(demo) Prav, priznam … {s['resnica']}", [s["nov_namig"]]

    vprasanje = _besede(sporocilo)
    kandidati = [(len(vprasanje & _besede(b)), nid, b) for nid, b in o["dejstva"].items()]
    kandidati.sort(key=lambda k: (-k[0], k[1] in igra.najdeni, random.random()))
    if kandidati and (kandidati[0][0] > 0 or kandidati[0][1] not in igra.najdeni):
        _, nid, besedilo = kandidati[0]
        return f"(demo) {uvod} {besedilo}", [nid]

    if random.random() < 0.5:
        return f"(demo) {uvod} {o['alibi']}", []
    return f"(demo) {random.choice(_IZMIKI)}", []
