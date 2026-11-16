# Tedensko poročilo – teden 1 (izbira teme, analiza, načrtovanje)

**Obdobje:** _od – do_ · **Pripravil:** _skrbnik dokumentacije_

## Izbrana tema
E – lastna ideja: detektivska igra »Kdo je kriv?«. Igralec zasliši osumljence, ki jih igra AI, in poišče krivca za izginulo ovojnico z maturitetnimi nalogami. Ker gre za lastno idejo, potrebujemo odobritev mentorja do konca tedna. _Status: odobreno dne ___ / čaka._

## Utemeljitev izbire AI
Preizkusili smo _(izpolni razvijalec AI po preizkusu)_:

| Merilo | Anthropic Claude (API) | Google Gemini (API) | Lokalni model (Ollama) |
|---|---|---|---|
| Slovenščina in igranje vloge | _ocena_ | _ocena_ | _ocena_ |
| Drži se navodil (ne izda skrivnosti) | _ocena_ | _ocena_ | _ocena_ |
| Odgovor v obliki JSON | da, vgrajeno (`output_config.format`) | _ocena_ | _ocena_ |
| Hitrost odgovora | _s_ | _s_ | _s_ |
| Cena / brezplačna kvota | _€ za 100 vprašanj_ | _€_ | brezplačno, a potrebuje zmogljiv računalnik |
| Zasebnost | podatki gredo v oblak | podatki gredo v oblak | podatki ostanejo na računalniku |

**Izbira:** _npr. Claude, ker …_. Ključni razlogi so dobra slovenščina, zanesljiv JSON odgovor in to, da se model drži vloge. Rezervna možnost je demo način brez AI.

## Sklepi uvodnega sestanka
- Vloge: _ime_ – AI, _ime_ – vmesnik, _ime_ – dokumentacija in testiranje.
- Resnico primera hrani koda, AI dobi samo podatke svoje vloge.
- Spletni vmesnik (Flask in HTML), brez dodatne strojne opreme.

## Opravljeno
- [ ] repozitorij na GitHubu, mentor dodan kot sodelavec
- [ ] struktura map, `.env.example`, `.gitignore`, osnutek README
- [ ] specifikacija na 1 stran (`docs/specifikacija.md`)
- [ ] skica vmesnika (`docs/skice/`)
- [ ] preizkus vsaj dveh AI storitev

## Načrt za teden 2
- AI: izboljšati navodila za osumljence in preveriti, da nihče ne izda skrivnosti pred časom (vsaj 20 poskusov »zvijačnih« vprašanj).
- Vmesnik: dokončati beležko z dokazi in gumb »Pokaži«, prilagoditi videz za telefon.
- Dokumentacija: seznam testnih primerov (`testi/testni-primeri.md`), osnutek poglavij priročnika.
