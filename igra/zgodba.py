"""
RESNICA PRIMERA – hrani jo samo koda.

AI nikoli ne dobi te datoteke v celoti. Vsak osumljenec dobi le svoje podatke
(glej igra/prompti.py). Skrivnosti se v navodila AI vključijo šele, ko jih
koda "odklene" – torej ko igralec osumljencu pokaže prave dokaze.
Zato AI ne more pomotoma izdati rešitve: dokler ni odklenjena, je preprosto ne pozna.
"""

PRIMER = {
    "naslov": "Izginula ovojnica",
    "uvod": (
        "Četrtek, 14.05. V zbornici je izginila zapečatena ovojnica s pisnimi "
        "nalogami za šolsko maturo. Prof. Lenarčič jo je ob 13.00 pustila v zbornici, "
        "ob 14.00 je ni bilo več. Ravnatelj vas prosi, da do jutra ugotovite, kdo jo je vzel. "
        "Zaslišite štiri osumljence, zbirajte dokaze v beležko in jih pokažite pravim osebam. "
        "Ko ste prepričani, obtožite krivca – imate samo en poskus."
    ),
    "krivec": "vesna",
    "razplet": (
        "Krivka je knjižničarka Vesna Hribar. Hišnik je med 13.20 in 13.50 pustil zbornico "
        "odklenjeno, ko je šel kadit. Vesna je za 15 minut zaprla knjižnico (listek »Takoj nazaj«), "
        "v modrem jopiču odšla v zbornico in vzela ovojnico, ker se je bala, da njen sin ne bo "
        "naredil mature. Ovojnico je skrila v škatlo za odpis knjig."
    ),
    # dokazi, ki dokazujejo krivdo (za končno oceno)
    "kljucni_namigi": ["N2", "N4", "N5", "N7"],
}

# Katalog vseh namigov (dokazov). Besedilo se pokaže v igralčevi beležki.
NAMIGI = {
    "N1": "Ovojnica je ležala na mizi v zbornici, ne zaklenjena v omari.",
    "N2": "Hišnik je zbornico med 13.20 in 13.50 pustil odklenjeno, ko je šel kadit.",
    "N3": "Tim je ob 13.30 videl hišnika kaditi na dvorišču.",
    "N4": "Tim je okoli 13.40 videl nekoga v modrem pletenem jopiču, ki je šel od zbornice proti knjižnici.",
    "N5": "Knjižnica je bila med 13.30 in 13.45 zaprta z listkom »Takoj nazaj«.",
    "N6": "Tim bi moral ob 13.30 biti pri športni vzgoji, ne na hodniku.",
    "N7": "Knjižničarka Vesna skoraj vedno nosi moder pleten jopič.",
    "N8": "Vesnin sin letos opravlja maturo in mu pri slovenščini ne gre dobro.",
    "N9": "Vesna je priznala: ovojnico je skrila v škatlo za odpis knjig v knjižnici.",
}

# Osumljenci. "dejstva" povedo prosto, "skrivnosti" šele, ko jim igralec pokaže
# VSE dokaze iz "odklene".
OSUMLJENCI = {
    "bojan": {
        "ime": "Bojan Kralj",
        "vloga": "hišnik",
        "znacaj": "Godrnjav, a dobrosrčen. Govori po domače, rad se pritožuje nad mladino. "
                  "Ne mara, da ga kdo obtožuje lenobe.",
        "alibi": "Ob 13.15 si v zbornici popravljal radiator, potem pa si imel delo v kleti.",
        "dejstva": {
            "N7": "Knjižničarka Vesna ima vedno oblečen tisti moder pleten jopič, tudi poleti.",
        },
        "skrivnosti": [
            {
                "namig_prikrivanja": "Nekaj prikrivaš glede tega, kaj si počel med 13.20 in 13.50. "
                                     "Ko kdo vpraša o tem, se izmikaš in poudarjaš, da si bil 'v kleti'.",
                "odklene": ["N3"],
                "resnica": "Priznaš, da nisi bil v kleti: šel si kadit na dvorišče in zbornico pustil "
                           "odklenjeno od 13.20 do 13.50. Sram te je, ker je to prepovedano.",
                "nov_namig": "N2",
            }
        ],
    },
    "mojca": {
        "ime": "Mojca Lenarčič",
        "vloga": "profesorica slovenščine",
        "znacaj": "Natančna, hitro užaljena, govori knjižno in malce vzvišeno. "
                  "Zelo ji je mar za svoj ugled.",
        "alibi": "Ovojnico si ob 13.00 pustila v zbornici in odšla na sestanek aktiva.",
        "dejstva": {
            "N1": "Ovojnico si pustila na mizi, ne v omari, ker si mislila, da se boš kmalu vrnila.",
            "N6": "Tim Zupan iz 4.b bi moral ob 13.30 biti pri športni vzgoji – to veš iz urnika.",
            "N8": "Vesnin sin je tvoj dijak; letos opravlja maturo in pri slovenščini mu ne gre dobro.",
        },
        "skrivnosti": [
            {
                "namig_prikrivanja": "Nekaj prikrivaš glede sestanka aktiva. Če kdo vztraja, "
                                     "zamenjaš temo.",
                "odklene": ["N2"],
                "resnica": "Priznaš, da sestanka ni bilo: ob 13.00 si šla k frizerju in ravnatelju "
                           "rekla, da si ovojnico zaklenila. Ovojnice nisi vzela.",
                "nov_namig": None,
            }
        ],
    },
    "tim": {
        "ime": "Tim Zupan",
        "vloga": "dijak 4.b",
        "znacaj": "Nervozen, govori hitro in uporablja mladinski sleng. Boji se, da bo kaznovan.",
        "alibi": "Bil si samo malo na hodniku, nič posebnega.",
        "dejstva": {
            "N3": "Ob 13.30 si skozi okno videl hišnika, ki je kadil na dvorišču.",
            "N4": "Okoli 13.40 si videl nekoga v modrem pletenem jopiču, ki je šel od zbornice proti "
                  "knjižnici. Obraza nisi videl.",
        },
        "skrivnosti": [
            {
                "namig_prikrivanja": "Ne poveš, zakaj nisi bil pri pouku, in se izmikaš vprašanjem o "
                                     "knjižnici.",
                "odklene": ["N6"],
                "resnica": "Priznaš, da si šprical športno vzgojo. Hotel si vrniti knjigo v knjižnico, "
                           "a je bila med 13.30 in 13.45 zaprta z listkom »Takoj nazaj«.",
                "nov_namig": "N5",
            }
        ],
    },
    "vesna": {
        "ime": "Vesna Hribar",
        "vloga": "knjižničarka",
        "znacaj": "Prijazna, mirna, materinska. Rada govori o knjigah in o svojem sinu. "
                  "Pod pritiskom postane kratka in se brani.",
        "alibi": "Ves čas si bila v knjižnici in je nisi zapustila.",
        "dejstva": {},
        "skrivnosti": [
            {
                "namig_prikrivanja": "Ves čas vztrajaš, da knjižnice nisi zapustila. Ko kdo omeni "
                                     "zbornico, jopič ali zaprto knjižnico, postaneš nemirna, a ne "
                                     "spremeniš zgodbe.",
                "odklene": ["N4", "N5"],
                "resnica": "Zlomiš se in priznaš: zaprla si knjižnico, šla v odklenjeno zbornico in "
                           "vzela ovojnico, ker si se bala za sina. Skrila si jo v škatlo za odpis "
                           "knjig v knjižnici. Zelo ti je žal.",
                "nov_namig": "N9",
            }
        ],
    },
}
