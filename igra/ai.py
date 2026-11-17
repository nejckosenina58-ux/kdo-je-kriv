"""Povezava z AI. Vsaka napaka se pretvori v AINapaka s prijaznim sporočilom za igralca."""

import json
import logging
import os
import re
import time

from .prompti import sestavi_navodila
from .stanje import Igra


_MODEL_LOG = logging.getLogger("igra.ai")


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
        # Brezplačni paket ima dnevno omejitev za VSAK model posebej, zato jih je več:
        # ko se enemu izteče kvota, igra preklopi na naslednjega.
        "model": "gemini-flash-latest,gemini-3.7-flash,gemini-3.6-flash,gemini-3.5-flash,"
                 "gemini-3-flash-preview,gemini-flash-lite-latest,gemini-3.5-flash-lite,gemini-3.1-flash-lite",
        "model_env": "GEMINI_MODEL",
        "napor": True,       # podpira reasoning_effort
    },
    "grok": {
        "kljuc": "XAI_API_KEY",
        "naslov": "https://api.x.ai/v1",
        "model": "grok-4.7",
        "model_env": "XAI_MODEL",
        "napor": False,
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


# --- skupni klic: navodila + pogovor -> JSON po shemi -------------------------------
def klic_json(sistem: str, sporocila: list[dict], shema: dict, *, ime_sheme: str,
              kdo: str, max_tokens: int = 4000, napor: str = "low",
              casovna_omejitev: float | None = None) -> str:
    """Pokliče izbrani AI in vrne surovo besedilo (JSON po shemi).

    `kdo` se uporabi v sporočilih o napakah (npr. ime osumljenca).
    """
    izbran = ponudnik()
    if izbran is None:
        raise AINapaka("AI ni nastavljen: na strežniku manjka GEMINI_API_KEY. Obvestite skrbnika igre.")
    omejitev = casovna_omejitev or float(os.getenv("AI_CASOVNA_OMEJITEV", "60"))
    if izbran == "anthropic":
        return _anthropic(sistem, sporocila, shema, kdo, max_tokens, napor, omejitev)
    return _openai_zdruzljiv(izbran, sistem, sporocila, shema, ime_sheme, kdo, max_tokens, napor, omejitev)


# --- odgovor osumljenca ---------------------------------------------------------------
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


def _opomba_ponovitve(igra: Igra, oseba: str, sporocilo: str) -> str:
    """Če detektiv ponovi vprašanje, modelu to povemo, da ne odgovori dobesedno enako."""
    prejsnja = [m["content"].strip().lower() for m in igra.zgodovina[oseba] if m["role"] == "user"]
    if sporocilo.strip().lower() in prejsnja:
        return ("\n\n[Opomba za vlogo: detektiv te to sprašuje že ponovno. Odgovori z drugimi besedami "
                "in pokaži, kako se zaradi tega počutiš.]")
    return ""


def odgovori(igra: Igra, oseba: str, sporocilo: str) -> tuple[str, list[str]]:
    """Vrne (besedilo odgovora, seznam novo najdenih namigov)."""
    sporocilo = odstrani_osebne_podatke(sporocilo.strip())[:500]
    if not sporocilo:
        raise AINapaka("Vprašanje je prazno. Napišite, kaj želite vprašati.")

    ime = igra.osumljenci[oseba]["ime"]
    surovo = klic_json(
        sestavi_navodila(igra, oseba),
        igra.zgodovina[oseba] + [{"role": "user",
                                  "content": sporocilo + _opomba_ponovitve(igra, oseba, sporocilo)}],
        SHEMA_ODGOVORA, ime_sheme="odgovor_osumljenca", kdo=ime,
    )
    besedilo, predlagani = _razcleni(surovo, ime)

    # Zgodovino posodobimo šele, ko je odgovor uspešen.
    igra.zgodovina[oseba].append({"role": "user", "content": sporocilo})
    igra.zgodovina[oseba].append({"role": "assistant", "content": besedilo})
    novi = igra.dodaj_namige(oseba, predlagani)   # koda preveri, ali je namig dovoljen
    return besedilo, novi


# --- Gemini / Grok (OpenAI-združljiv API) ----------------------------------------
_odjemalci: dict = {}
_PRESKOCI: dict[str, float] = {}   # model -> do kdaj ga preskakujemo (porabljena kvota, ne obstaja)


def _dobi_openai_odjemalca(izbran: str):
    if izbran not in _odjemalci:
        from openai import OpenAI
        nast = OPENAI_ZDRUZLJIVI[izbran]
        _odjemalci[izbran] = OpenAI(
            api_key=_kljuc(nast["kljuc"]),
            base_url=nast["naslov"],
            max_retries=0,   # ob 429/503 raje takoj preklopimo na naslednji model
        )
    return _odjemalci[izbran]


def _openai_zdruzljiv(izbran, sistem, sporocila, shema, ime_sheme, kdo, max_tokens, napor, omejitev) -> str:
    import openai

    nast = OPENAI_ZDRUZLJIVI[izbran]
    napacen_kljuc = f"Ključ za AI ({nast['kljuc']}) ni veljaven. Obvestite skrbnika igre."
    dodatno = {"reasoning_effort": napor} if nast["napor"] else {}
    vsi = [m.strip() for m in os.getenv(nast["model_env"], nast["model"]).split(",") if m.strip()]
    zdaj = time.time()
    modeli = [m for m in vsi if _PRESKOCI.get(m, 0) < zdaj] or vsi
    odjemalec = _dobi_openai_odjemalca(izbran).with_options(timeout=omejitev)
    for i, model in enumerate(modeli):
        zadnji = i == len(modeli) - 1
        try:
            odziv = odjemalec.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": sistem}] + sporocila,
                max_tokens=max_tokens,
                response_format={
                    "type": "json_schema",
                    "json_schema": {"name": ime_sheme, "schema": shema, "strict": True},
                },
                **dodatno,
            )
            break
        except (openai.RateLimitError, openai.InternalServerError, openai.NotFoundError,
                openai.APITimeoutError) as e:
            # kvota tega modela je porabljena, model je preobremenjen ali ne obstaja -> naslednji
            if isinstance(e, openai.NotFoundError):
                _PRESKOCI[model] = zdaj + 24 * 3600
            elif isinstance(e, openai.RateLimitError) and "per day" in str(e.body).lower():
                _PRESKOCI[model] = zdaj + 3600            # čez eno uro poskusimo znova
            else:
                _PRESKOCI[model] = zdaj + 600             # preobremenjen ali prepočasen: 10 minut premora
            _MODEL_LOG.warning("Model %s ni na voljo (%s), poskušam naslednjega.", model, type(e).__name__)
            if zadnji:
                _pretvori_napako(e, kdo, napacen_kljuc)
        except openai.APIError as e:
            _pretvori_napako(e, kdo, napacen_kljuc)
    return _preveri_izbiro(odziv, kdo)


def _pretvori_napako(e, kdo: str, napacen_kljuc: str):
    """OpenAI-SDK napako pretvori v AINapaka s slovenskim sporočilom."""
    import openai
    try:
        raise e
    except openai.APITimeoutError:
        raise AINapaka(f"{kdo} predolgo razmišlja (AI se ni odzval pravočasno). Poskusite znova.")
    except openai.APIConnectionError:
        raise AINapaka("Ni povezave z AI storitvijo. Preverite internetno povezavo in poskusite znova.")
    except openai.AuthenticationError:
        raise AINapaka(napacen_kljuc)
    except openai.PermissionDeniedError:
        raise AINapaka("Račun za AI nima dostopa ali kredita. Obvestite skrbnika igre.")
    except openai.RateLimitError as e:
        if "per day" in str(e.body).lower():
            raise AINapaka("Dnevna omejitev brezplačnega AI paketa je porabljena za vse modele. "
                           "Poskusite znova jutri ali uporabite drug ključ.")
        raise AINapaka("Preveč vprašanj naenkrat (dosežena omejitev brezplačnega paketa). "
                       "Počakajte minuto in poskusite znova.")
    except openai.APIStatusError as e:
        if e.status_code == 400 and "api key" in f"{e.message} {e.body}".lower():   # Gemini in xAI vrneta 400
            raise AINapaka(napacen_kljuc)
        if e.status_code in (502, 503, 504):
            raise AINapaka(f"{kdo} se ravno ne more zbrati (AI je preobremenjen). Poskusite čez nekaj sekund.")
        raise AINapaka(f"AI storitev trenutno ne deluje (napaka {e.status_code}). Poskusite čez nekaj minut.")


def _preveri_izbiro(odziv, kdo: str) -> str:
    if not odziv.choices:
        raise AINapaka(f"{kdo} je samo molče skomignil z rameni (prazen odgovor AI). Poskusite znova.")
    izbira = odziv.choices[0]
    if getattr(izbira.message, "refusal", None):
        raise AINapaka(f"{kdo} na to vprašanje noče odgovoriti. Poskusite ga vprašati drugače.")
    if izbira.finish_reason == "length":
        raise AINapaka(f"{kdo} se je zapletel v predolg odgovor. Poskusite s krajšim vprašanjem.")
    return izbira.message.content or ""


# --- Anthropic Claude -----------------------------------------------------------
_odjemalec = None


def _dobi_odjemalca():
    global _odjemalec
    if _odjemalec is None:
        import anthropic
        _odjemalec = anthropic.Anthropic(max_retries=1)
    return _odjemalec


def _anthropic(sistem, sporocila, shema, kdo, max_tokens, napor, omejitev) -> str:
    import anthropic

    model = os.getenv("AI_MODEL", "claude-opus-5-5")
    parametri = dict(
        model=model,
        max_tokens=max_tokens,
        system=sistem,
        messages=sporocila,
        output_config={"effort": napor, "format": {"type": "json_schema", "schema": shema}},
    )
    try:
        odjemalec = _dobi_odjemalca().with_options(timeout=omejitev)
        if model in MODELI_Z_NADOMESTNIM and os.getenv("AI_NADOMESTNI_MODEL", "1") == "1":
            odziv = odjemalec.beta.messages.create(
                betas=["server-side-fallback-2026-07-01"], fallbacks="default", **parametri)
        else:
            odziv = odjemalec.messages.create(**parametri)
    except anthropic.APITimeoutError:
        raise AINapaka(f"{kdo} predolgo razmišlja (AI se ni odzval pravočasno). Poskusite znova.")
    except anthropic.APIConnectionError:
        raise AINapaka("Ni povezave z AI storitvijo. Preverite internetno povezavo in poskusite znova.")
    except anthropic.AuthenticationError:
        raise AINapaka("Ključ za AI ni veljaven. Obvestite skrbnika igre.")
    except anthropic.RateLimitError:
        raise AINapaka("Preveč vprašanj naenkrat. Počakajte pol minute in poskusite znova.")
    except anthropic.APIStatusError as e:
        raise AINapaka(f"AI storitev trenutno ne deluje (napaka {e.status_code}). Poskusite čez nekaj minut.")

    if odziv.stop_reason == "refusal":
        raise AINapaka(f"{kdo} na to vprašanje noče odgovoriti. Poskusite ga vprašati drugače.")
    if odziv.stop_reason == "max_tokens":
        raise AINapaka(f"{kdo} se je zapletel v predolg odgovor. Poskusite s krajšim vprašanjem.")
    return next((b.text for b in odziv.content if b.type == "text"), "")
