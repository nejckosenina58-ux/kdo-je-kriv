"""Povezava z AI. Vsaka napaka se pretvori v AINapaka s prijaznim sporočilom za igralca."""

import json
import os
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


# --- izbira ponudnika ------------------------------------------------------------
def _kljuc(ime: str) -> str:
    kljuc = os.getenv(ime, "").strip()
    return "" if kljuc in ("", "vas-kljuc-tukaj") else kljuc


# Ponudniki z OpenAI-združljivim API-jem: ključ, naslov, privzeti model, nastavitev modela.
OPENAI_ZDRUZLJIVI = {
    "gemini": {
        "kljuc": "GEMINI_API_KEY",
        "naslov": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "model": "gemini-flash-latest",
        "model_env": "GEMINI_MODEL",
        "dodatno": {"reasoning_effort": "low"},   # hitrejši kratki odgovori
    },
    "grok": {
        "kljuc": "XAI_API_KEY",
        "naslov": "https://api.x.ai/v1",
        "model": "grok-4.7",
        "model_env": "XAI_MODEL",
        "dodatno": {},
    },
}


def ponudnik() -> str | None:
    """Kateri AI igra osumljence: "gemini", "grok", "anthropic" ali None (ni ključa).

    Če je nastavljenih več ključev, velja ta vrstni red.
    """
    for ime, nast in OPENAI_ZDRUZLJIVI.items():
        if _kljuc(nast["kljuc"]):
            return ime
    if _kljuc("ANTHROPIC_API_KEY"):
        return "anthropic"
    return None


def ai_nastavljen() -> bool:
    """Ali ima strežnik ključ za AI. Brez njega osumljenci ne morejo odgovarjati."""
    return ponudnik() is not None


def _ima_kljuc() -> bool:
    return bool(_kljuc("ANTHROPIC_API_KEY"))


def _razcleni(surovo: str, ime: str) -> tuple[str, list[str]]:
    """Iz JSON odgovora modela izlušči besedilo in seznam razkritih namigov."""
    surovo = (surovo or "").strip()
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


# --- glavni vstop --------------------------------------------------------------
def odgovori(igra: Igra, oseba: str, sporocilo: str) -> tuple[str, list[str]]:
    """Vrne (besedilo odgovora, seznam novo najdenih namigov)."""
    sporocilo = odstrani_osebne_podatke(sporocilo.strip())[:500]
    if not sporocilo:
        raise AINapaka("Vprašanje je prazno. Napišite, kaj želite vprašati.")

    izbran = ponudnik()
    if izbran in OPENAI_ZDRUZLJIVI:
        besedilo, predlagani = _openai_zdruzljiv(izbran, igra, oseba, sporocilo)
    elif izbran == "anthropic":
        besedilo, predlagani = _anthropic(igra, oseba, sporocilo)
    else:
        raise AINapaka("AI ni nastavljen: na strežniku manjka GEMINI_API_KEY. Obvestite skrbnika igre.")

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
            raise AINapaka("AI ni nastavljen: na strežniku manjka ANTHROPIC_API_KEY. "
                           "Obvestite skrbnika igre.")
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

    surovo = next((b.text for b in odziv.content if b.type == "text"), "")
    return _razcleni(surovo, ime)


def _opomba_ponovitve(igra: Igra, oseba: str, sporocilo: str) -> str:
    """Če detektiv ponovi vprašanje, modelu to povemo, da ne odgovori dobesedno enako."""
    prejsnja = [m["content"].strip().lower() for m in igra.zgodovina[oseba] if m["role"] == "user"]
    if sporocilo.strip().lower() in prejsnja:
        return ("\n\n[Opomba za vlogo: detektiv te to sprašuje že ponovno. Odgovori z drugimi besedami "
                "in pokaži, kako se zaradi tega počutiš.]")
    return ""


# --- Gemini / Grok (OpenAI-združljiv API) ----------------------------------------
_odjemalci: dict = {}


def _dobi_openai_odjemalca(izbran: str):
    if izbran not in _odjemalci:
        from openai import OpenAI
        nast = OPENAI_ZDRUZLJIVI[izbran]
        _odjemalci[izbran] = OpenAI(
            api_key=_kljuc(nast["kljuc"]),
            base_url=nast["naslov"],
            timeout=float(os.getenv("AI_CASOVNA_OMEJITEV", "60")),
            max_retries=3,   # brezplačni paketi občasno vrnejo 503 (preobremenjeno)
        )
    return _odjemalci[izbran]


def _openai_zdruzljiv(izbran: str, igra: Igra, oseba: str, sporocilo: str) -> tuple[str, list[str]]:
    import openai

    nast = OPENAI_ZDRUZLJIVI[izbran]
    ime = OSUMLJENCI[oseba]["ime"]
    napacen_kljuc = f"Ključ za AI ({nast['kljuc']}) ni veljaven. Obvestite skrbnika igre."
    sporocila = (
        [{"role": "system", "content": sestavi_navodila(igra, oseba)}]
        + igra.zgodovina[oseba]
        + [{"role": "user", "content": sporocilo + _opomba_ponovitve(igra, oseba, sporocilo)}]
    )
    try:
        odziv = _dobi_openai_odjemalca(izbran).chat.completions.create(
            model=os.getenv(nast["model_env"], nast["model"]),
            messages=sporocila,
            max_tokens=4000,
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "odgovor_osumljenca", "schema": SHEMA_ODGOVORA, "strict": True},
            },
            **nast["dodatno"],
        )
    except openai.APITimeoutError:
        raise AINapaka(f"{ime} predolgo razmišlja (AI se ni odzval pravočasno). Poskusite znova.")
    except openai.APIConnectionError:
        raise AINapaka("Ni povezave z AI storitvijo. Preverite internetno povezavo in poskusite znova.")
    except openai.AuthenticationError:
        raise AINapaka(napacen_kljuc)
    except openai.PermissionDeniedError:
        raise AINapaka("Račun za AI nima dostopa ali kredita. Obvestite skrbnika igre.")
    except openai.RateLimitError:
        raise AINapaka("Preveč vprašanj naenkrat (dosežena omejitev brezplačnega paketa). "
                       "Počakajte minuto in poskusite znova.")
    except openai.APIStatusError as e:
        if e.status_code == 400 and "api key" in f"{e.message} {e.body}".lower():   # Gemini in xAI vrneta 400
            raise AINapaka(napacen_kljuc)
        if e.status_code in (502, 503, 504):
            raise AINapaka(f"{ime} se ravno ne more zbrati (AI je preobremenjen). Poskusite čez nekaj sekund.")
        raise AINapaka(f"AI storitev trenutno ne deluje (napaka {e.status_code}). Poskusite čez nekaj minut.")

    if not odziv.choices:
        raise AINapaka(f"{ime} je samo molče skomignil z rameni (prazen odgovor AI). Poskusite znova.")
    izbira = odziv.choices[0]
    if getattr(izbira.message, "refusal", None):
        raise AINapaka(f"{ime} na to vprašanje noče odgovoriti. Poskusite ga vprašati drugače.")
    if izbira.finish_reason == "length":
        raise AINapaka(f"{ime} se je zapletel v predolg odgovor. Poskusite s krajšim vprašanjem.")
    return _razcleni(izbira.message.content, ime)
