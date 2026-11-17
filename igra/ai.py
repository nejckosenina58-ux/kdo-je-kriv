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


def ponudnik() -> str | None:
    """Kateri AI igra osumljence: "grok" (xAI), "anthropic" (Claude) ali None (ni ključa).

    Grok ima prednost, če sta nastavljena oba ključa.
    """
    if _kljuc("XAI_API_KEY"):
        return "grok"
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
    if izbran == "grok":
        besedilo, predlagani = _grok(igra, oseba, sporocilo)
    elif izbran == "anthropic":
        besedilo, predlagani = _anthropic(igra, oseba, sporocilo)
    else:
        raise AINapaka("AI ni nastavljen: na strežniku manjka XAI_API_KEY. Obvestite skrbnika igre.")

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


# --- xAI Grok (OpenAI-združljiv API) ---------------------------------------------
_grok_odjemalec = None


def _dobi_grok_odjemalca():
    global _grok_odjemalec
    if _grok_odjemalec is None:
        from openai import OpenAI
        _grok_odjemalec = OpenAI(
            api_key=_kljuc("XAI_API_KEY"),
            base_url=os.getenv("XAI_BASE_URL", "https://api.x.ai/v1"),
            timeout=float(os.getenv("AI_CASOVNA_OMEJITEV", "30")),
            max_retries=1,
        )
    return _grok_odjemalec


def _grok(igra: Igra, oseba: str, sporocilo: str) -> tuple[str, list[str]]:
    import openai

    ime = OSUMLJENCI[oseba]["ime"]
    sporocila = (
        [{"role": "system", "content": sestavi_navodila(igra, oseba)}]
        + igra.zgodovina[oseba]
        + [{"role": "user", "content": sporocilo}]
    )
    try:
        odziv = _dobi_grok_odjemalca().chat.completions.create(
            model=os.getenv("XAI_MODEL", "grok-4.7"),
            messages=sporocila,
            max_tokens=4000,
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "odgovor_osumljenca", "schema": SHEMA_ODGOVORA, "strict": True},
            },
        )
    except openai.APITimeoutError:
        raise AINapaka(f"{ime} predolgo razmišlja (AI se ni odzval pravočasno). Poskusite znova.")
    except openai.APIConnectionError:
        raise AINapaka("Ni povezave z AI storitvijo. Preverite internetno povezavo in poskusite znova.")
    except openai.AuthenticationError:
        raise AINapaka("Ključ za AI (XAI_API_KEY) ni veljaven. Obvestite skrbnika igre.")
    except openai.PermissionDeniedError:
        raise AINapaka("Račun za AI nima dostopa ali kredita. Obvestite skrbnika igre.")
    except openai.RateLimitError:
        raise AINapaka("Preveč vprašanj naenkrat. Počakajte pol minute in poskusite znova.")
    except openai.APIStatusError as e:
        if e.status_code == 400 and "api key" in f"{e.message} {e.body}".lower():   # xAI vrne 400 za napačen ključ
            raise AINapaka("Ključ za AI (XAI_API_KEY) ni veljaven. Obvestite skrbnika igre.")
        raise AINapaka(f"AI storitev trenutno ne deluje (napaka {e.status_code}). Poskusite čez nekaj minut.")

    if not odziv.choices:
        raise AINapaka(f"{ime} je samo molče skomignil z rameni (prazen odgovor AI). Poskusite znova.")
    izbira = odziv.choices[0]
    if getattr(izbira.message, "refusal", None):
        raise AINapaka(f"{ime} na to vprašanje noče odgovoriti. Poskusite ga vprašati drugače.")
    if izbira.finish_reason == "length":
        raise AINapaka(f"{ime} se je zapletel v predolg odgovor. Poskusite s krajšim vprašanjem.")
    return _razcleni(izbira.message.content, ime)
