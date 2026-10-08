# Birddeck

Un program în linie de comandă care transformă o zonă într-un pachet Anki cu păsările observate acolo. Include fotografii, înregistrări audio și numele comune și științifice. Fișierele media sunt incluse în pachet, astfel încât îl poți studia offline.

[English documentation](README.md)

## Instalare

Ai nevoie de Python 3.11 sau mai nou:

```sh
git clone https://github.com/aiocafea/birddeck.git
cd birddeck
python -m venv .venv
source .venv/bin/activate
python -m pip install .
```

Pe Windows, activează mediul cu `.venv\Scripts\activate` în Command Prompt sau `.venv\Scripts\Activate.ps1` în PowerShell. Pe Debian/Ubuntu poate fi necesar pachetul `python3-venv`.

Nu ai nevoie de cont sau cheie API. Generarea necesită internet; studiul în Anki funcționează offline.

## Alegerea zonei

```sh
birddeck places Bucharest --lang ro
birddeck build --location "Bucharest" --lang ro --output pasari.apkg
```

Dacă sunt mai multe rezultate, programul te lasă să alegi. Pentru scripturi sau pentru a folosi exact aceeași zonă, transmite identificatorul afișat de căutare:

```sh
birddeck build --place 11745 --limit 20 --lang ro --output bucuresti.apkg
```

Un ID folosește conturul zonei din iNaturalist. Coordonatele permit alegerea unui cerc în jurul oricărui punct:

```sh
birddeck build --lat 44.4268 --lon 26.1025 --radius 25 \
  --limit 30 --lang ro --output imprejurimi.apkg
```

Raza este în kilometri: mai mare decât zero, maximum 500, implicit 25. Poți căuta orice zonă din catalogul iNaturalist; dacă numele nu apare, încearcă altă denumire sau coordonate. Într-un script, un nume ambiguu produce o listă și o eroare; aplicația nu selectează singură primul rezultat.

## Cartonașe și limbă

Implicit sunt create toate cele patru tipuri disponibile:

| Opțiune | Față | Verso |
| --- | --- | --- |
| `image-name` | Imagine | Nume comun și științific |
| `name-image` | Nume | Imagine |
| `audio-name` | Sunet | Nume |
| `name-audio` | Nume | Sunet |

Exemplu doar pentru recunoaștere, cu observații din luna mai:

```sh
birddeck build --place 11745 --cards image-name,audio-name \
  --month 5 --lang ro --output primavara.apkg
```

`--lang ro` și `--lang en` schimbă limba interfeței, întrebărilor și numelor comune. Când lipsește traducerea, se folosește numele englezesc disponibil, apoi cel științific. Opțiunile CLI și unele diagnostice tehnice rămân în engleză.

Deschide fișierul `.apkg` în Anki prin **File → Import**. Raportul alăturat, `.manifest.json`, conține sursele și eventualele omisiuni. Autorul, licența și sursa fiecărui fișier apar pe verso.

## Ce înseamnă „comune”

Selecția folosește numărul observațiilor iNaturalist de nivel research grade, pentru păsări care nu sunt marcate captive. Nu măsoară efectivul populațiilor: o zonă cu mulți observatori poate influența mult clasamentul. `--month` selectează o lună din toți anii, nu prezice ce vei întâlni într-o excursie.

Fotografiile și sunetele sunt exemple ale speciei și pot proveni din alte regiuni. O înregistrare poate conține strigăte sau zgomot de fond; programul nu garantează că este un cântec izolat. Dacă nu găsește audio utilizabil, omite cartonașele audio ale acelei specii și consemnează motivul.

`--licenses personal`, implicit, permite fișiere Creative Commons, inclusiv licențe necomerciale și fără opere derivate. `--licenses free` limitează selecția la CC0, CC BY și CC BY-SA. Licența MIT a codului nu se aplică fișierelor descărcate; acestea își păstrează propriile condiții de utilizare. [Explicațiile iNaturalist](https://help.inaturalist.org/en/support/solutions/articles/151000169918) descriu licențele media.

## Repetarea generării

Răspunsurile API sunt păstrate în cache 24 de ore, iar media se reutilizează. `--refresh` descarcă din nou datele; `--cache DIRECTOR` schimbă directorul cache. Rulează o singură generare odată pentru același director.

Pentru un export nou, alege alt nume de fișier. Aceleași specii, direcții, zonă, limbă și lună primesc aceiași identificatori Anki, astfel încât o reimportare poate actualiza notițele existente conform setărilor Anki. Un export mai mic nu șterge cartonașele vechi.

Comanda `birddeck --lang ro build --help` afișează opțiunile. Detaliile de dezvoltare și testare sunt în [README-ul principal](README.md#development).
