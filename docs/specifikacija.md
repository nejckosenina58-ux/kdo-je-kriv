# Specifikacija – »Kdo je kriv?« (1 stran)

**Skupina:** _ime 1_ (razvijalec AI), _ime 2_ (vmesnik), _ime 3_ (dokumentacija in testiranje) · **Razred:** _4.x_ · **Mentor:** _ime_ · **Tema:** E – lastna ideja (potrebna odobritev mentorja)

## Kaj izdelek dela
Spletna detektivska igra. Igralec rešuje skrivnost: iz zbornice je izginila ovojnica z maturitetnimi nalogami. Zasliši štiri osumljence (hišnik, profesorica, dijak, knjižničarka). Vsakega igra AI s svojim značajem, alibijem in skrivnostmi. Igralec zbira dokaze v beležko in jih pokaže osumljencem. Ko pokaže prave dokaze, osumljenec prizna svojo skrivnost. Na koncu igralec obtoži enega osumljenca in izve razplet.

## Za koga
Dijaki in obiskovalci informativnega dne. Igra traja 10–20 minut in ne zahteva tehničnega znanja.

## Katero AI uporablja
Jezikovni model **Anthropic Claude** prek API-ja (Python SDK `anthropic`). Za primerjavo preizkusimo še Google Gemini in en lokalni model prek Ollame. Utemeljitev izbire je v tedenskem poročilu.

## Ključni trik: resnico hrani koda, ne AI
- Kdo je kriv, kje je ovojnica in kateri dokazi kaj odklenejo, piše samo v kodi (`igra/zgodba.py`).
- Vsak osumljenec dobi **samo svoje** podatke: alibi, kar ve, in namig, da nekaj prikriva. Resnice o svoji skrivnosti ne dobi.
- Ko igralec pokaže prave dokaze, **koda** doda resnico v navodila tega osumljenca. Šele takrat jo AI lahko pove.
- AI vrne odgovor v obliki JSON (`odgovor` in `razkriti_namigi`). Koda preveri, ali je oseba ta namig sploh smela povedati, in šele nato ga vpiše v beležko.

## Skica delovanja
```
 Igralec (brskalnik)                 Strežnik (Python/Flask)                        AI (Claude)
 ┌──────────────┐  vprašanje   ┌──────────────────────────────────┐  navodila za   ┌───────────┐
 │ izbere osebo │ ───────────▶ │ 1. odstrani osebne podatke       │  to osebo +    │ odgovori  │
 │ vpraša /     │              │ 2. sestavi navodila samo iz      │  zgodovina     │ v vlogi   │
 │ pokaže dokaz │              │    podatkov te osebe             │ ─────────────▶ │ (JSON)    │
 │              │ ◀─────────── │ 3. preveri namige, posodobi      │ ◀───────────── │           │
 │ beležka      │  odgovor +   │    beležko (resnica v zgodba.py) │                └───────────┘
 │ obtožba      │  nov dokaz   │ 4. ob napaki prijazno sporočilo  │
 └──────────────┘              └──────────────────────────────────┘
```

## Varnost in zasebnost
API ključ je v datoteki `.env` (ni na GitHubu). Igra ne snema glasu ali slik. Pred pošiljanjem v AI odstrani e-pošto, telefonske številke in EMŠO. Na zaslonu je ves čas opozorilo, da se AI lahko moti. Ob izpadu AI igra ne pade, ampak pokaže prijazno sporočilo. Za predstavitve brez interneta ima način `demo`.
