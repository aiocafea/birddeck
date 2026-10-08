# Birddeck

Turn a place into an Anki deck of its most-observed birds. Pick a town, an iNaturalist place ID, or a circle on the map using coordinates. Get photographs and recordings inside an `.apkg` file, ready to study offline.

[Instrucțiuni în română](README.ro.md)

```console
$ birddeck places Bucharest
1. Bucharest, RO  [ID: 11745]
2. IOR–Titan, Bucharest — “Aici stă un arici” project area, BI, RO  [ID: 240819]
3. Bucharest ring road  [ID: 194369]

$ birddeck build --place 11745 --limit 20 --lang en --output bucharest.apkg
```

No account or API key is needed. Internet access is needed while generating a deck. Anki does not need internet access to show the included media.

## Install

Python 3.11 or newer:

```sh
git clone https://github.com/aiocafea/birddeck.git
cd birddeck
python -m venv .venv
source .venv/bin/activate
python -m pip install .
```

On Windows, activate with `.venv\Scripts\activate` in Command Prompt, or `.venv\Scripts\Activate.ps1` in PowerShell. On Debian/Ubuntu, install `python3-venv` if creating the environment fails.

Open the resulting `.apkg` through **File → Import** in Anki.

## Choose a location

Search and choose interactively:

```sh
birddeck build --location "Bucharest" --output birds.apkg
```

Names can match several places. In a terminal, Birddeck asks which one you mean. In scripts, it prints the matches and exits; pass `--place ID` to make the choice explicit.

A place ID uses that place's boundary. To use a distance from a point instead:

```sh
birddeck build --lat 44.4268 --lon 26.1025 --radius 25 \
  --limit 30 --lang ro --output bucuresti.apkg
```

The radius is in kilometres, from greater than zero to 500; the default is 25. `--radius` applies only to coordinates. Place names are searched in iNaturalist's place catalogue, so a neighbourhood may require coordinates or a different spelling.

## Choose what to study

All four directions are enabled by default. Select any subset with `--cards`:

| Value | Front | Back |
| --- | --- | --- |
| `image-name` | Photo | Common and scientific names |
| `name-image` | Names | Photo |
| `audio-name` | Recording | Names |
| `name-audio` | Names | Recording |

```sh
birddeck build --place 11745 --cards image-name,audio-name \
  --month 5 --lang en --output spring-birds.apkg
```

`--month` filters observations by calendar month across all years, which helps separate summer and winter visitors. It is not a forecast. `--limit` accepts 1–100 species.

`--lang ro` switches the help text, progress messages, card prompts and common names to Romanian; `--lang en` selects English. A missing common name falls back to the API's English name, then the scientific name. Flags and diagnostic details from network libraries remain in English. Run `birddeck build --help` for the full interface.

## Where the birds and media come from

The [iNaturalist API](https://api.inaturalist.org/v1/docs/) supplies the places, species counts, photographs and recordings. Species are ordered by the number of research-grade, non-captive observations in the selected area. That measures what people recorded, not how many birds actually live there. Heavily visited parks and easy-to-photograph species can dominate.

The ranking is local; media examples can come from anywhere in the world. Photos use the taxon's default photo where its license permits, then fall back to observation photos. Audio comes from observations of that species, ordered by observation votes. Recordings may include calls, other species and background noise. They are not automatically trimmed or classified as songs, and regional vocal differences are possible.

Birddeck examines up to 30 observations per media lookup and tries up to five downloadable, licensed candidates. Missing media is reported rather than replaced with an unrelated bird or a blank card. A species with a photo but no usable recording still gets photo cards.

Each run writes two files:

- `birds.apkg`: notes, cards and the media they reference.
- `birds.manifest.json`: query area, observation counts, media URLs, attribution, license codes and missing-media reasons.

The default `--licenses personal` admits Creative Commons media, including noncommercial and no-derivatives licenses. `--licenses free` restricts the selection to CC0, CC BY and CC BY-SA. Each asset is checked separately, and attribution appears on the card's answer. The code's MIT license does **not** cover downloaded photos or recordings; their own terms still apply. See [iNaturalist's media licensing explanation](https://help.inaturalist.org/en/support/solutions/articles/151000169918).

## Repeat runs

API responses are cached for 24 hours; downloaded media is reused. Use `--refresh` to bypass both, or `--cache PATH` to choose the cache directory. The default is `$XDG_CACHE_HOME/birddeck`, or `~/.cache/birddeck`.

Existing output files are never deliberately overwritten: choose a new filename. Notes have stable IDs based on area, language, month, species and card direction, so importing a later export of the same selection lets Anki recognise existing notes. Import settings control whether their content is updated. A smaller export does not delete old cards from Anki.

Requests use timeouts, retry transient failures and HTTP 429 responses, and pace fresh API lookups at roughly one per second, following [iNaturalist's recommendations](https://www.inaturalist.org/pages/api+recommended+practices). Individual downloads are capped at 20 MiB. Run one build at a time per cache directory.

## Development

```sh
python -m pip install -e '.[dev]'
pytest -q
ruff check .
ruff format --check .
```

The tests run without network access. They open generated `.apkg` archives and inspect the SQLite collection and bundled media, as well as exercising license filtering, incomplete media, stable note IDs, unsafe download URLs and ambiguous place selection. CI runs them on Linux and Windows.

The application is split into four small modules: `cli.py` handles arguments and language, `api.py` owns HTTP and caching, `domain.py` defines areas/species/media, and `deck.py` builds notes and the export. There is no server or database to maintain.

Current limits: one photo and one recording per species, no manual media picker, and no promise of complete coverage in sparsely observed areas. A recording preview/selection command would be the next useful addition.
