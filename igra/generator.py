"""AI za vsako igro izmisli nov primer. Koda nato preveri, da je primer rešljiv.

Rezultat ima enako obliko kot privzeti primer v igra/zgodba.py:
{"primer": {...}, "namigi": {"N1": "..."}, "osumljenci": {"o1": {...}}}

Celoten primer (tudi krivec) ostane samo na strežniku. Vsak osumljenec v pogovoru
še vedno dobi le svoje podatke (glej igra/prompti.py).
"""

import json
import logging
import random

from .ai import AINapaka, klic_json

log = logging.getLogger(__name__)

# Naključni izhodišči, da je vsak primer drugačen.
KRAJI = [
    "gimnazija v manjšem mestu", "dijaški dom", "šolska ekskurzija v Ljubljani", "planinska koča na Pohorju",
    "mestni muzej", "gledališče med generalko", "hotel ob morju v Piranu", "smučarski tabor na Kaninu",
    "tehniški muzej", "radijska postaja", "šolski bal", "turistična kmetija na Dolenjskem",
    "knjižnica med nočjo knjige", "kuharsko tekmovanje", "kampiranje ob Soči", "festival v Mariboru",
    "športna dvorana pred finalom", "glasbena šola pred koncertom", "botanični vrt", "vlak na poti v Koper",
]
DOGODKI = [
    "izginila je dragocena stvar", "nekdo je poškodoval pomemben predmet", "izginil je denar iz blagajne",
    "nekdo je zamenjal rezultate tekmovanja", "izginil je ključ, ki odpira nekaj pomembnega",
    "nekdo je ukradel recept ali načrt", "nekdo je pokvaril pripravo prireditve",
    "izginila je trofeja ali nagrada", "izginil je prenosnik s pomembnimi podatki",
]

_NAMIG = {"type": "object", "properties": {"id": {"type": "string"}, "besedilo": {"type": "string"}},
          "required": ["id", "besedilo"], "additionalProperties": False}
_DEJSTVO = {"type": "object", "properties": {"namig": {"type": "string"}, "besedilo": {"type": "string"}},
            "required": ["namig", "besedilo"], "additionalProperties": False}
_SKRIVNOST = {
    "type": "object",
    "properties": {
        "namig_prikrivanja": {"type": "string"},
        "odklene": {"type": "array", "items": {"type": "string"}},
        "resnica": {"type": "string"},
        "nov_namig": {"type": "string"},
    },
    "required": ["namig_prikrivanja", "odklene", "resnica", "nov_namig"],
    "additionalProperties": False,
}
_OSUMLJENEC = {
    "type": "object",
    "properties": {
        "id": {"type": "string"}, "ime": {"type": "string"}, "vloga": {"type": "string"},
        "znacaj": {"type": "string"}, "alibi": {"type": "string"},
        "dejstva": {"type": "array", "items": _DEJSTVO},
        "skrivnost": _SKRIVNOST,
    },
    "required": ["id", "ime", "vloga", "znacaj", "alibi", "dejstva", "skrivnost"],
    "additionalProperties": False,
}
SHEMA_PRIMERA = {
    "type": "object",
    "properties": {
        "naslov": {"type": "string"}, "kraj": {"type": "string"}, "dogodek": {"type": "string"},
        "uvod": {"type": "string"}, "razplet": {"type": "string"}, "krivec": {"type": "string"},
        "namigi": {"type": "array", "items": _NAMIG},
        "osumljenci": {"type": "array", "items": _OSUMLJENEC},
        "kljucni_namigi": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["naslov", "kraj", "dogodek", "uvod", "razplet", "krivec",
                 "namigi", "osumljenci", "kljucni_namigi"],
    "additionalProperties": False,
}

NAVODILA = """Si avtor detektivskih ugank za slovenske srednješolce. Izmisli NOV, izviren primer
za igro, v kateri detektiv (igralec) zasliši štiri osumljence, ki jih igra AI.

VSEBINA:
- Vse v slovenščini. Izmišljene osebe; "ime" je vedno IME IN PRIIMEK (npr. "Nina Kos"), ne resnične osebe.
- Primerno za šolo: kraja, poškodba, prevara, izginotje predmeta. Brez umora, nasilja, drog in spolnosti.
- Konkretne ure (npr. 18.20), prostori in predmeti, da lahko detektiv sklepa.
- Vsak osumljenec ima jasen značaj in način govora.

ZGRADBA (OBVEZNO – koda jo preveri):
- Natanko 4 osumljenci z id "o1", "o2", "o3", "o4". "krivec" je id enega od njih.
- 8 do 10 namigov z id "N1", "N2", ... Besedilo namiga je kratko dejstvo v tretji osebi,
  kot zapis v detektivovi beležki.
- Vsak namig ima NATANKO ENEGA lastnika: ali je v "dejstva" točno enega osumljenca
  (to pove prosto, ko ga vprašaš), ali je "nov_namig" skrivnosti točno enega osumljenca
  (to pove šele, ko prizna). Noben namig ni pri dveh osebah.
- V "dejstva" je "besedilo" zapisano v drugi osebi, kot navodilo igralcu vloge
  (npr. "Ob 18.20 si videl …"). Vsaj trije osumljenci imajo vsaj eno dejstvo.
- Vsak osumljenec ima eno skrivnost:
  - "namig_prikrivanja": kaj prikriva in kako se izmika (v drugi osebi).
  - "odklene": ID-ji namigov, ki mu jih mora detektiv pokazati, da prizna. Ti namigi morajo
    pripadati DRUGIM osumljencem, nikoli njemu samemu.
  - "resnica": kaj prizna (v drugi osebi).
  - "nov_namig": ID namiga, ki ga s priznanjem razkrije, ali "" če ne razkrije novega namiga.
- Nedolžni osumljenci prikrivajo nekaj nerodnega, a nepovezanega s krajo (rdeči sledi).
  Vsaj eden od njih s priznanjem razkrije nov namig, ki je potreben za razkritje krivca.
- Krivčeva skrivnost ima v "odklene" vsaj DVA namiga, "nov_namig" pa je namig s krivčevim
  priznanjem (npr. kje je skril ukradeno).
- Primer mora biti rešljiv po korakih: z dejstvi, ki jih osebe povedo prosto, detektiv odklene
  nekatere skrivnosti, ti novi namigi odklenejo naslednje, na koncu pa krivčevo priznanje.
- "kljucni_namigi": 3 do 5 namigov, ki skupaj dokazujejo krivdo.
- "dogodek": 1–2 stavka, kaj se je zgodilo (to vedo vsi). "kraj": kratko, kje.
- "uvod": 3–4 stavki za igralca: kaj se je zgodilo in naloga. Na koncu dodaj: "Zaslišite štiri
  osumljence, zbirajte dokaze v beležko in jih pokažite pravim osebam. Ko ste prepričani,
  obtožite krivca – imate samo en poskus."
- "razplet": 2–4 stavki, ki razložijo, kdo je kriv, kako in zakaj (pokaže se šele na koncu).
- Krivec naj ne bo najbolj očiten osumljenec."""


def _preveri(p: dict) -> dict:
    """Preveri in pretvori AI primer v notranjo obliko. Ob napaki vrže ValueError z razlogom."""
    namigi = {}
    for n in p.get("namigi", []):
        nid, bes = str(n["id"]).strip().upper(), str(n["besedilo"]).strip()
        if not bes or nid in namigi:
            raise ValueError(f"namig {nid} je prazen ali podvojen")
        namigi[nid] = bes
    if not 6 <= len(namigi) <= 12:
        raise ValueError(f"število namigov je {len(namigi)}, mora biti 8 do 10")

    osumljenci, lastnik = {}, {}
    for o in p.get("osumljenci", []):
        oid = str(o["id"]).strip().lower()
        if oid in osumljenci:
            raise ValueError(f"osumljenec {oid} je podvojen")
        for polje in ("ime", "vloga", "znacaj", "alibi"):
            if not str(o[polje]).strip():
                raise ValueError(f"osumljenec {oid} nima polja {polje}")
        dejstva = {}
        for d in o["dejstva"]:
            nid = str(d["namig"]).strip().upper()
            if nid not in namigi:
                raise ValueError(f"{oid} ima dejstvo z neobstoječim namigom {nid}")
            if nid in lastnik:
                raise ValueError(f"namig {nid} ima dva lastnika ({lastnik[nid]} in {oid})")
            lastnik[nid] = oid
            dejstva[nid] = str(d["besedilo"]).strip()
        s = o["skrivnost"]
        nov = str(s["nov_namig"]).strip().upper() or None
        if nov:
            if nov not in namigi:
                raise ValueError(f"skrivnost osebe {oid} razkrije neobstoječ namig {nov}")
            if nov in lastnik:
                raise ValueError(f"namig {nov} ima dva lastnika ({lastnik[nov]} in {oid})")
            lastnik[nov] = oid
        odklene = sorted({str(n).strip().upper() for n in s["odklene"]})
        if not odklene:
            raise ValueError(f"skrivnosti osebe {oid} ni mogoče odkleniti (prazen 'odklene')")
        osumljenci[oid] = {
            "ime": str(o["ime"]).strip(), "vloga": str(o["vloga"]).strip(),
            "znacaj": str(o["znacaj"]).strip(), "alibi": str(o["alibi"]).strip(),
            "dejstva": dejstva,
            "skrivnosti": [{"namig_prikrivanja": str(s["namig_prikrivanja"]).strip(), "odklene": odklene,
                            "resnica": str(s["resnica"]).strip(), "nov_namig": nov}],
        }
    if len(osumljenci) != 4:
        raise ValueError(f"število osumljencev je {len(osumljenci)}, mora biti 4")

    # Namig brez lastnika, ki ga nihče ne potrebuje, preprosto odstranimo.
    potrebni = {n for o in osumljenci.values() for n in o["skrivnosti"][0]["odklene"]}
    for n in set(namigi) - set(lastnik):
        if n in potrebni:
            raise ValueError(f"namig {n} nima lastnika, a ga potrebuje skrivnost; dodaj ga nekomu")
        del namigi[n]
    for oid, o in osumljenci.items():
        for n in o["skrivnosti"][0]["odklene"]:
            if n not in namigi:
                raise ValueError(f"skrivnost osebe {oid} zahteva neobstoječ namig {n}")
            if lastnik[n] == oid:
                raise ValueError(f"skrivnost osebe {oid} zahteva namig {n}, ki ga ima sam")

    krivec = str(p["krivec"]).strip().lower()
    if krivec not in osumljenci:
        raise ValueError(f"krivec '{krivec}' ni med osumljenci")
    ks = osumljenci[krivec]["skrivnosti"][0]
    if not ks["nov_namig"]:
        raise ValueError("krivčeva skrivnost mora imeti 'nov_namig' s priznanjem")
    if len(ks["odklene"]) < 2:
        raise ValueError("krivčeva skrivnost mora zahtevati vsaj dva namiga")

    # Ali je primer rešljiv? Simuliramo igralca, ki pokaže vse, kar ima.
    najdeni = {n for o in osumljenci.values() for n in o["dejstva"]}
    spremenjeno = True
    while spremenjeno:
        spremenjeno = False
        for o in osumljenci.values():
            s = o["skrivnosti"][0]
            if s["nov_namig"] and s["nov_namig"] not in najdeni and set(s["odklene"]) <= najdeni:
                najdeni.add(s["nov_namig"])
                spremenjeno = True
    nedosegljivi = set(namigi) - najdeni
    if nedosegljivi:
        raise ValueError(f"primer ni rešljiv: namigov {sorted(nedosegljivi)} ni mogoče dobiti")

    kljucni = [str(n).strip().upper() for n in p["kljucni_namigi"] if str(n).strip().upper() in namigi]
    if not kljucni:
        raise ValueError("ni ključnih namigov")

    primer = {k: str(p[k]).strip() for k in ("naslov", "kraj", "dogodek", "uvod", "razplet")}
    if not all(primer.values()):
        raise ValueError("naslov, kraj, dogodek, uvod ali razplet je prazen")
    primer.update(krivec=krivec, kljucni_namigi=kljucni)
    return {"primer": primer, "namigi": namigi, "osumljenci": osumljenci}


def ustvari_primer(poskusov: int = 3) -> dict:
    """Ustvari nov rešljiv primer. Če AI ne uspe, vrže AINapaka."""
    kraj, dogodek = random.choice(KRAJI), random.choice(DOGODKI)
    sporocila = [{"role": "user", "content":
                  f"Izmisli nov primer. Kraj: {kraj}. Kaj se je zgodilo: {dogodek}. "
                  f"Naključna številka za navdih: {random.randint(1000, 9999)}."}]
    zadnja_napaka = "neznana napaka"
    for poskus in range(1, poskusov + 1):
        surovo = klic_json(NAVODILA, sporocila, SHEMA_PRIMERA, ime_sheme="detektivski_primer",
                           kdo="Pisatelj primera", max_tokens=16000, napor="low",
                           casovna_omejitev=90)
        try:
            return _preveri(json.loads(surovo))
        except (json.JSONDecodeError, KeyError, TypeError, AttributeError) as e:
            zadnja_napaka = f"neveljaven JSON ({e})"
        except ValueError as e:
            zadnja_napaka = str(e)
        log.warning("Ustvarjen primer ni veljaven (poskus %d): %s", poskus, zadnja_napaka)
        sporocila += [{"role": "assistant", "content": surovo},
                      {"role": "user", "content": f"Primer ni veljaven: {zadnja_napaka}. "
                                                  "Popravi to in vrni celoten popravljen primer."}]
    raise AINapaka(f"AI ni uspel sestaviti rešljivega primera ({zadnja_napaka}).")
