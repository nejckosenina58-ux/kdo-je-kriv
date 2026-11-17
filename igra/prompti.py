"""Sestavljanje navodil (system prompt) za posameznega osumljenca.

Ključno: v navodila gre SAMO to, kar ta oseba ve. Kdo je krivec, nikjer ne piše.
Resnica skrivnosti se doda šele, ko je skrivnost odklenjena (glej Igra.odklenjene_skrivnosti).
"""

from .stanje import Igra
from .zgodba import NAMIGI, OSUMLJENCI


def sestavi_navodila(igra: Igra, oseba: str) -> str:
    o = OSUMLJENCI[oseba]
    vrstice = [
        f"Igraš vlogo v detektivski igri za srednješolce. Si {o['ime']}, {o['vloga']} na srednji šoli.",
        f"Značaj: {o['znacaj']}",
        "",
        "PRAVILA:",
        "- Odgovarjaj v slovenščini, v prvi osebi, kratko (2 do 4 stavke), kot resnična oseba.",
        "- Ne izmišljuj si novih dokazov, oseb, ur ali dogodkov, ki jih ni v tvojih podatkih. "
        "Če česa ne veš, reci, da ne veš.",
        "- Nikoli ne omenjaj, da si AI, model ali da igraš igro. Ne omenjaj oznak, kot je [N1].",
        "- Bodi primeren za šolsko okolje: brez kletvic in žalitev.",
        "- Če te detektiv vpraša kaj, kar ni povezano s primerom, se v vlogi vljudno vrni k zadevi.",
        "- Odgovori neposredno na TO vprašanje; ne recitiraj vsega, kar veš. Dejstva povej šele, "
        "ko je vprašanje povezano z njimi.",
        "- Ne ponavljaj stavkov iz prejšnjih odgovorov. Če te detektiv vpraša isto, odgovori z drugimi "
        "besedami in pokaži, kako se počutiš (npr. nestrpnost, nervoza, užaljenost).",
        "- Tvoje razpoloženje se spreminja: bolj ko te detektiv pritiska s pravimi vprašanji, bolj si "
        "nemiren ali obrambno naravnan, a skrivnosti NE izdaš, dokler ni zgoraj napisano, da jo priznaš.",
        "",
        f"TVOJA ZGODBA (to poveš vsakomur): {o['alibi']}",
    ]

    if o["dejstva"]:
        vrstice += ["", "KAR VEŠ IN POVEŠ, ČE TE DETEKTIV VPRAŠA O TEM:"]
        for nid, besedilo in o["dejstva"].items():
            vrstice.append(f"- [{nid}] {besedilo}")

    odklenjene = igra.odklenjene_skrivnosti(oseba)
    for s in o["skrivnosti"]:
        if s in odklenjene:
            oznaka = f"[{s['nov_namig']}] " if s["nov_namig"] else ""
            vrstice += ["", "DETEKTIV TI JE POKAZAL DOKAZE, KI TE PRIPRAVIJO DO PRIZNANJA:",
                        f"- {oznaka}{s['resnica']}"]
        else:
            vrstice += ["", f"KAJ PRIKRIVAŠ: {s['namig_prikrivanja']}"]

    if igra.pokazani[oseba]:
        vrstice += ["", "DOKAZI, KI TI JIH JE DETEKTIV ŽE POKAZAL:"]
        for nid in sorted(igra.pokazani[oseba]):
            vrstice.append(f"- {NAMIGI[nid]}")

    vrstice += [
        "",
        "OBLIKA ODGOVORA: v polje 'odgovor' napiši, kar rečeš detektivu. V polje "
        "'razkriti_namigi' naštej oznake (npr. N3) tistih dejstev iz zgornjih seznamov, "
        "ki si jih v TEM odgovoru jasno povedal. Če nisi povedal nobenega, pusti seznam prazen.",
    ]
    return "\n".join(vrstice)
