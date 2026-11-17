# Kdo je kriv? – detektivska igra z AI osumljenci

Šolski projekt (6 tednov). Igralec zasliši štiri osumljence, ki jih igra jezikovni model, zbira dokaze in obtoži krivca.
Navodila za igralce brez tehničnega znanja so v uporabniškem priročniku (`docs/prirocnik.pdf`, nastaja). Ta README je namenjen razvijalcem.

## Ekipa
| Vloga | Ime |
|---|---|
| Razvijalec AI rešitve | _Nace Gantar_ |
| Razvijalec vmesnika | _Žiga Korez_ |
| Skrbnik dokumentacije in testiranja | _Nejc Košenina_ |
| Mentor | _Prof. Matic Holobar_ |

## Hiter zagon (razvojno okolje)
Potrebujete Python 3.10 ali novejšega.

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows  (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env        # Linux/macOS: cp .env.example .env
```
V `.env` vpišite svoj `GEMINI_API_KEY` (brezplačen ključ: https://aistudio.google.com/apikey). Vse osumljence igra AI (privzeto Google Gemini, seznam modelov v `GEMINI_MODEL`; podprta sta tudi Grok z `XAI_API_KEY` in Claude z `ANTHROPIC_API_KEY`), zato igra brez ključa ne deluje – vmesnik takrat pokaže rdeč trak »AI ni povezan«.

### Objava na Renderju (pravi AI)
V Render → *Environment* dodajte `GEMINI_API_KEY` (spremenljivko `AI_PONUDNIK` lahko izbrišete, ni več v uporabi). Nato *Manual Deploy*. Če je na strani rdeč trak »AI ni povezan«, ključ ni nastavljen.

```bash
python app.py
```
Nato odprite http://localhost:5000.
Public domena: https://kdo-je-kriv.onrender.com/

## Struktura
```
app.py               Flask strežnik in API (/api/nova-igra, /api/vprasaj, /api/pokazi, /api/obtozi)
igra/zgodba.py       klasični primer »Izginula ovojnica« (osumljenci, dokazi, krivec)
igra/generator.py    AI za vsako igro izmisli nov primer; koda preveri, da je rešljiv
gunicorn.conf.py     nastavitve za Render (daljša časovna omejitev za ustvarjanje primera)
igra/stanje.py       stanje igre: beležka, pokazani dokazi, odklepanje skrivnosti, obtožba
igra/prompti.py      sestavi navodila (system prompt) samo iz podatkov ene osebe
igra/ai.py           klic Gemini / Grok (OpenAI-združljiv API) ali Claude API, strukturiran JSON odgovor, obravnava napak
templates/index.html spletni vmesnik (HTML + JS, brez knjižnic)
docs/                specifikacija, priročnik, skice
porocila/            dnevna in tedenska poročila, dnevnik uporabe AI
testi/               testni primeri in rezultati testiranja z uporabniki
```

## Kako deluje AI del
1. `prompti.sestavi_navodila()` sestavi navodila za izbranega osumljenca: značaj, alibi, dejstva z oznakami (`[N3]`) in namig, da nekaj prikriva. Kdo je krivec, ne piše nikjer.
2. Ko igralec osumljencu pokaže vse dokaze, ki jih skrivnost zahteva (`odklene`), `Igra.odklenjene_skrivnosti()` vrne to skrivnost. Šele takrat gre njena resnica v navodila.
3. Model vrne JSON po shemi (Gemini in Grok: `response_format` z `json_schema`; Claude: `output_config.format`): `{"odgovor": "...", "razkriti_namigi": ["N3"]}`.
4. `Igra.dodaj_namige()` sprejme samo namige, ki jih ta oseba v tem trenutku sme razkriti. Če si model kaj izmisli, ne pride v beležko.

Nastavitve klica: `effort: "low"` (kratki pogovorni odgovori), časovna omejitev iz `AI_CASOVNA_OMEJITEV`, 1 ponovni poskus. Pri modelih, ki to podpirajo, je vklopljen strežniški nadomestni model ob zavrnitvi (`fallbacks: "default"`). Izklopite ga z `AI_NADOMESTNI_MODEL=0`.

## Obravnava napak
Vsaka napaka (časovna omejitev, ni povezave, napačen ključ, preveč zahtev, zavrnitev, prazen ali neveljaven odgovor) se v `igra/ai.py` pretvori v `AINapaka` s slovenskim sporočilom za igralca. Strežnik vrne kodo 503, vmesnik pa sporočilo pokaže v pogovoru. Igra ne pade.

## Varnost
- `.env` je v `.gitignore`. Ključev nikoli ne pišemo v kodo.
- `odstrani_osebne_podatke()` pred pošiljanjem v AI zamenja e-pošto, telefonske številke in EMŠO.
- Igra ne shranjuje pogovorov na disk. Ob ponovnem zagonu strežnika se izbrišejo.

## Delo z Gitom
- `main` vsebuje vedno delujočo različico. Vsak razvija na svoji veji (`ai/...`, `vmesnik/...`, `docs/...`).
- Vsaka sprememba gre v `main` prek pull requesta, ki ga pregleda še en član ekipe.
- Napake in naloge beležimo v GitHub Issues.

## Nov primer v vsaki igri
Gumb **Nov primer** od AI zahteva nov primer (naključen kraj in dogodek iz `igra/generator.py`). AI vrne JSON po shemi `SHEMA_PRIMERA`, `_preveri()` pa ga preveri: 4 osumljenci, vsak namig ima enega lastnika, skrivnosti se odklepajo z namigi drugih oseb, krivčevo priznanje je dosegljivo (koda simulira igralca). Če primer ni veljaven, AI dobi razlog in ga popravi (do 3 poskusi). Če ne uspe, se igra klasični primer z opozorilom. Gumb **Klasični primer** ali `ZGODBA=privzeta` v `.env` vedno igra »Izginula ovojnica«.

Celoten primer (tudi krivec) ostane na strežniku; vsak osumljenec v pogovoru dobi le svoje podatke.

**Omejitve brezplačnega Gemini paketa:** približno 20 zahtev na dan za vsak model. Zato `GEMINI_MODEL` vsebuje seznam modelov, ločen z vejicami: ko enemu poteče kvota ali je preobremenjen, igra uporabi naslednjega.

## Pisanje klasične zgodbe
Klasični primer spreminjate v `igra/zgodba.py`. Vsak namig v `NAMIGI` mora imeti točno enega lastnika: ali ga oseba pove prosto (v `dejstva`) ali je `nov_namig` neke skrivnosti. Vsaka skrivnost v `odklene` potrebuje namige, ki jih igralec lahko dobi pri **drugih** osebah, sicer igre ni mogoče rešiti.
