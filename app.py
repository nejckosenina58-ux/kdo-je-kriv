"""Spletni strežnik igre »Kdo je kriv?«. Zagon: python app.py, nato odprite http://localhost:5000"""

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

load_dotenv()

import os                                                     # noqa: E402

from igra.ai import AINapaka, ai_nastavljen, odgovori         # noqa: E402  (po load_dotenv)
from igra.generator import ustvari_primer                     # noqa: E402
from igra.stanje import Igra                                  # noqa: E402

app = Flask(__name__)
IGRE: dict[str, Igra] = {}   # igre v pomnilniku (dovolj za šolski prototip)


def _igra():
    igra = IGRE.get((request.json or {}).get("igra", ""))
    if igra is None:
        return None, (jsonify(napaka="Igra ne obstaja več. Začnite novo igro."), 404)
    if igra.konec:
        return None, (jsonify(napaka="Igra je končana. Začnite novo igro."), 400)
    return igra, None


def _oseba(igra: Igra):
    oseba = (request.json or {}).get("oseba")
    return oseba if oseba in igra.osumljenci else None


@app.get("/")
def domov():
    return render_template("index.html")


@app.post("/api/nova-igra")
def nova_igra():
    """Vsaka nova igra dobi nov primer, ki ga izmisli AI.

    {"klasicna": true} ali ZGODBA=privzeta v .env igra privzeti primer »Izginula ovojnica«.
    Če AI primera ne uspe sestaviti, se igra privzeti primer z opozorilom.
    """
    klasicna = bool((request.get_json(silent=True) or {}).get("klasicna"))
    klasicna = klasicna or os.getenv("ZGODBA", "").strip().lower() == "privzeta" or not ai_nastavljen()
    opozorilo = None
    zgodba = None
    if not klasicna:
        try:
            zgodba = ustvari_primer()
        except AINapaka as e:
            opozorilo = f"Novega primera ni bilo mogoče ustvariti ({e}) Igrate klasični primer."
        except Exception:
            app.logger.exception("Napaka pri ustvarjanju primera")
            opozorilo = "Novega primera ni bilo mogoče ustvariti. Igrate klasični primer."
    igra = Igra(zgodba)
    IGRE[igra.id] = igra
    return jsonify(
        igra=igra.id,
        ai=ai_nastavljen(),
        opozorilo=opozorilo,
        naslov=igra.primer["naslov"],
        uvod=igra.primer["uvod"],
        osumljenci=[{"id": k, "ime": o["ime"], "vloga": o["vloga"]}
                    for k, o in igra.osumljenci.items()],
    )


@app.post("/api/vprasaj")
def vprasaj():
    igra, napaka = _igra()
    if napaka:
        return napaka
    oseba = _oseba(igra)
    if not oseba:
        return jsonify(napaka="Najprej izberite osumljenca."), 400
    try:
        besedilo, novi = odgovori(igra, oseba, str(request.json.get("besedilo", "")))
    except AINapaka as e:
        return jsonify(napaka=str(e)), 503
    except Exception:                    # zadnja varovalka – igra ne sme pasti
        app.logger.exception("Nepričakovana napaka")
        return jsonify(napaka="Prišlo je do nepričakovane napake. Poskusite znova."), 500
    return jsonify(odgovor=besedilo, novi=[{"id": n, "besedilo": igra.namigi[n]} for n in novi],
                   belezka=igra.belezka())


@app.post("/api/pokazi")
def pokazi():
    """Igralec osumljencu pokaže dokaz iz beležke. Koda zabeleži, AI se odzove."""
    igra, napaka = _igra()
    if napaka:
        return napaka
    oseba, namig = _oseba(igra), request.json.get("namig")
    if not oseba or namig not in igra.najdeni:
        return jsonify(napaka="Pokažete lahko samo dokaz iz svoje beležke."), 400
    igra.pokazani[oseba].add(namig)
    try:
        besedilo, novi = odgovori(igra, oseba, f"Detektiv ti pokaže dokaz: »{igra.namigi[namig]}« Kaj porečeš na to?")
    except AINapaka as e:
        return jsonify(napaka=str(e)), 503
    except Exception:
        app.logger.exception("Nepričakovana napaka")
        return jsonify(napaka="Prišlo je do nepričakovane napake. Poskusite znova."), 500
    return jsonify(odgovor=besedilo, novi=[{"id": n, "besedilo": igra.namigi[n]} for n in novi],
                   belezka=igra.belezka())


@app.post("/api/obtozi")
def obtozi():
    igra, napaka = _igra()
    if napaka:
        return napaka
    oseba = _oseba(igra)
    if not oseba:
        return jsonify(napaka="Izberite, koga obtožujete."), 400
    return jsonify(igra.obtozi(oseba))


if not ai_nastavljen():
    app.logger.warning("GEMINI_API_KEY ni nastavljen – osumljenci ne bodo mogli odgovarjati.")

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=False)
