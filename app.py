"""Spletni strežnik igre »Kdo je kriv?«. Zagon: python app.py, nato odprite http://localhost:5000"""

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

load_dotenv()

from igra.ai import AINapaka, odgovori          # noqa: E402  (po load_dotenv)
from igra.stanje import Igra                    # noqa: E402
from igra.zgodba import NAMIGI, OSUMLJENCI, PRIMER  # noqa: E402

app = Flask(__name__)
IGRE: dict[str, Igra] = {}   # igre v pomnilniku (dovolj za šolski prototip)


def _igra():
    igra = IGRE.get((request.json or {}).get("igra", ""))
    if igra is None:
        return None, (jsonify(napaka="Igra ne obstaja več. Začnite novo igro."), 404)
    if igra.konec:
        return None, (jsonify(napaka="Igra je končana. Začnite novo igro."), 400)
    return igra, None


def _oseba():
    oseba = (request.json or {}).get("oseba")
    return oseba if oseba in OSUMLJENCI else None


@app.get("/")
def domov():
    return render_template("index.html")


@app.post("/api/nova-igra")
def nova_igra():
    igra = Igra()
    IGRE[igra.id] = igra
    return jsonify(
        igra=igra.id,
        naslov=PRIMER["naslov"],
        uvod=PRIMER["uvod"],
        osumljenci=[{"id": k, "ime": o["ime"], "vloga": o["vloga"]}
                    for k, o in OSUMLJENCI.items()],
    )


@app.post("/api/vprasaj")
def vprasaj():
    igra, napaka = _igra()
    if napaka:
        return napaka
    oseba = _oseba()
    if not oseba:
        return jsonify(napaka="Najprej izberite osumljenca."), 400
    try:
        besedilo, novi = odgovori(igra, oseba, str(request.json.get("besedilo", "")))
    except AINapaka as e:
        return jsonify(napaka=str(e)), 503
    except Exception:                    # zadnja varovalka – igra ne sme pasti
        app.logger.exception("Nepričakovana napaka")
        return jsonify(napaka="Prišlo je do nepričakovane napake. Poskusite znova."), 500
    return jsonify(odgovor=besedilo, novi=[{"id": n, "besedilo": NAMIGI[n]} for n in novi],
                   belezka=igra.belezka())


@app.post("/api/pokazi")
def pokazi():
    """Igralec osumljencu pokaže dokaz iz beležke. Koda zabeleži, AI se odzove."""
    igra, napaka = _igra()
    if napaka:
        return napaka
    oseba, namig = _oseba(), request.json.get("namig")
    if not oseba or namig not in igra.najdeni:
        return jsonify(napaka="Pokažete lahko samo dokaz iz svoje beležke."), 400
    igra.pokazani[oseba].add(namig)
    try:
        besedilo, novi = odgovori(igra, oseba, f"Detektiv ti pokaže dokaz: »{NAMIGI[namig]}« Kaj porečeš na to?")
    except AINapaka as e:
        return jsonify(napaka=str(e)), 503
    except Exception:
        app.logger.exception("Nepričakovana napaka")
        return jsonify(napaka="Prišlo je do nepričakovane napake. Poskusite znova."), 500
    return jsonify(odgovor=besedilo, novi=[{"id": n, "besedilo": NAMIGI[n]} for n in novi],
                   belezka=igra.belezka())


@app.post("/api/obtozi")
def obtozi():
    igra, napaka = _igra()
    if napaka:
        return napaka
    oseba = _oseba()
    if not oseba:
        return jsonify(napaka="Izberite, koga obtožujete."), 400
    return jsonify(igra.obtozi(oseba))


if __name__ == "__main__":
    import os
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=False)
