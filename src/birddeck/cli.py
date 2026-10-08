import argparse
import os
import sys
from pathlib import Path

from .api import Client
from .deck import build
from .domain import CARD_TYPES, Area, BirddeckError

TEXT = {
    "en": {
        "description": "Make offline Anki cards for the birds around a place.",
        "places": "Find a place and its iNaturalist ID",
        "build": "Create an .apkg deck and a source manifest",
        "lang": "Interface and common-name language (default: en)",
        "location": "Search by place name; choose a result if ambiguous",
        "place": "Exact iNaturalist place ID (administrative/project boundary)",
        "lat": "Latitude of the centre; also requires --lon",
        "lon": "Longitude of the centre",
        "radius": "Circle radius in km, only with --lat/--lon (default: 25)",
        "limit": "Number of most-observed species, 1–100 (default: 20)",
        "cards": "Comma-separated card types, or all (default: all)",
        "month": "Filter observations by month, 1–12, across all years",
        "licenses": "personal: Creative Commons; free: CC0/BY/BY-SA only",
        "output": "New .apkg output path (existing files are never replaced)",
        "cache": "API and media cache directory",
        "refresh": "Bypass cached responses and media",
        "query": "Place name, e.g. Bucharest",
        "choose": "Choose a number (Enter cancels): ",
        "ambiguous": "Several places match. Run again with --place ID from the list.",
        "none": "No matching places. Try another name or coordinates.",
        "cancel": "Cancelled.",
        "error": "Error",
        "ranking": "Ranking by iNaturalist observations, not population abundance.",
        "done": "Created {cards} cards for {species} species: {output}",
        "missing": "Species with missing media: {count}. See {manifest}",
        "area": "Area",
    },
    "ro": {
        "description": "Creează cartonașe Anki offline cu păsările dintr-o zonă.",
        "places": "Caută o zonă și identificatorul ei iNaturalist",
        "build": "Creează un pachet .apkg și raportul surselor",
        "lang": "Limba interfeței și a numelor comune (implicit: en)",
        "location": "Caută după numele zonei; alege un rezultat dacă sunt mai multe",
        "place": "ID exact iNaturalist (limita administrativă/a proiectului)",
        "lat": "Latitudinea centrului; necesită și --lon",
        "lon": "Longitudinea centrului",
        "radius": "Raza în km, doar cu --lat/--lon (implicit: 25)",
        "limit": "Numărul speciilor cu cele mai multe observații, 1–100 (implicit: 20)",
        "cards": "Tipuri separate prin virgulă sau all (implicit: all)",
        "month": "Filtrează observațiile după lună, 1–12, din toți anii",
        "licenses": "personal: Creative Commons; free: doar CC0/BY/BY-SA",
        "output": "Calea noului fișier .apkg (fișierele existente nu se suprascriu)",
        "cache": "Directorul cache pentru API și fișiere media",
        "refresh": "Descarcă din nou răspunsurile și fișierele media",
        "query": "Numele zonei, de exemplu București",
        "choose": "Alege numărul (Enter anulează): ",
        "ambiguous": "Sunt mai multe zone. Rulează din nou cu --place ID din listă.",
        "none": "Nicio zonă găsită. Încearcă alt nume sau coordonate.",
        "cancel": "Anulat.",
        "error": "Eroare",
        "ranking": "Clasament după observațiile iNaturalist, nu după mărimea populațiilor.",
        "done": "Am creat {cards} cartonașe pentru {species} specii: {output}",
        "missing": "Specii cu fișiere lipsă: {count}. Detalii: {manifest}",
        "area": "Zona",
    },
}


def language(argv):
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--lang", choices=("ro", "en"), default="en")
    return pre.parse_known_args(argv)[0].lang


def parser(lang):
    t = TEXT[lang]
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--lang", choices=("ro", "en"), default=argparse.SUPPRESS, help=t["lang"])
    common.add_argument("--cache", type=Path, default=argparse.SUPPRESS, help=t["cache"])
    common.add_argument(
        "--refresh", action="store_true", default=argparse.SUPPRESS, help=t["refresh"]
    )
    root = argparse.ArgumentParser(description=t["description"], parents=[common])
    root.set_defaults(
        lang=lang,
        cache=Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "birddeck",
        refresh=False,
    )
    sub = root.add_subparsers(dest="command", required=True)
    places = sub.add_parser("places", help=t["places"], parents=[common])
    places.add_argument("query", help=t["query"])
    export = sub.add_parser("build", help=t["build"], parents=[common])
    area = export.add_mutually_exclusive_group(required=True)
    area.add_argument("--location", help=t["location"])
    area.add_argument("--place", type=int, help=t["place"])
    area.add_argument("--lat", type=float, help=t["lat"])
    export.add_argument("--lon", type=float, help=t["lon"])
    export.add_argument("--radius", type=float, help=t["radius"])
    export.add_argument("--limit", type=int, default=20, help=t["limit"])
    export.add_argument("--cards", default="all", help=t["cards"])
    export.add_argument("--month", type=int, help=t["month"])
    export.add_argument(
        "--licenses", choices=("personal", "free"), default="personal", help=t["licenses"]
    )
    export.add_argument("--output", type=Path, required=True, help=t["output"])
    return root


def show_places(places):
    for i, place in enumerate(places, 1):
        print(f"{i}. {place['display_name']}  [ID: {place['id']}]")


def resolve_area(args, client, t):
    if args.lat is not None:
        if args.lon is None:
            raise BirddeckError("--lat + --lon")
        radius = 25 if args.radius is None else args.radius
        return Area(
            f"{args.lat:g}, {args.lon:g} / {radius:g} km", lat=args.lat, lon=args.lon, radius=radius
        )
    if args.lon is not None or args.radius is not None:
        raise BirddeckError("--lon / --radius: --lat + --lon")
    if args.place is not None:
        if args.place < 1:
            raise BirddeckError("--place: > 0")
        results = client.get(f"places/{args.place}")["results"]
    else:
        results = client.places(args.location)
    if not results:
        raise BirddeckError(t["none"])
    if len(results) == 1:
        selected = results[0]
    else:
        show_places(results)
        if not sys.stdin.isatty():
            raise BirddeckError(t["ambiguous"])
        try:
            choice = input(t["choose"])
            if not choice:
                raise BirddeckError(t["cancel"])
            index = int(choice)
            if not 1 <= index <= len(results):
                raise ValueError
            selected = results[index - 1]
        except (ValueError, EOFError) as exc:
            raise BirddeckError(t["ambiguous"]) from exc
    return Area(selected["display_name"], place_id=selected["id"])


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    lang = language(argv)
    args = parser(lang).parse_args(argv)
    t = TEXT[lang]
    client = None
    try:
        if args.command == "build":
            cards = (
                CARD_TYPES if args.cards == "all" else tuple(dict.fromkeys(args.cards.split(",")))
            )
            if not cards or any(c not in CARD_TYPES for c in cards):
                raise BirddeckError("--cards: " + ", ".join(CARD_TYPES))
            if not 1 <= args.limit <= 100:
                raise BirddeckError("--limit: 1–100")
            if args.month is not None and not 1 <= args.month <= 12:
                raise BirddeckError("--month: 1–12")
            if args.output.suffix != ".apkg":
                raise BirddeckError("--output: .apkg")
            if args.output.exists() or args.output.with_suffix(".manifest.json").exists():
                raise BirddeckError(f"File exists / Fișier existent: {args.output}")
        client = Client(args.cache, args.refresh)
        if args.command == "places":
            places = client.places(args.query)
            if not places:
                raise BirddeckError(t["none"])
            show_places(places)
            return 0
        area = resolve_area(args, client, t)
        print(f"{t['area']}: {area.label}", file=sys.stderr)
        print(t["ranking"], file=sys.stderr)
        report = build(
            client,
            area,
            args.output,
            limit=args.limit,
            lang=lang,
            cards=cards,
            month=args.month,
            license_policy=args.licenses,
            progress=lambda msg: print(msg, file=sys.stderr),
        )
        count = sum(bool(s["cards"]) for s in report["species"])
        print(t["done"].format(cards=report["cards_created"], species=count, output=args.output))
        missing = sum(bool(s["missing"]) for s in report["species"])
        print(
            t["missing"].format(count=missing, manifest=args.output.with_suffix(".manifest.json"))
        )
        return 0
    except (BirddeckError, OSError, ValueError) as exc:
        print(f"{t['error']}: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print(t["cancel"], file=sys.stderr)
        return 130
    finally:
        if client:
            client.close()
