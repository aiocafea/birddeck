import hashlib
import html
import json
import tempfile
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import genanki

from .domain import BirddeckError

CSS = """
.card { font-family: Arial, sans-serif; text-align: center; font-size: 23px;
        color: #243e36; background: #f7f5ef; padding: 24px; }
img { max-width: 100%; max-height: 420px; border-radius: 6px; }
.scientific { font-style: italic; font-size: 17px; margin-top: 8px; }
.source { font-size: 12px; line-height: 1.6; margin-top: 24px; }
a { color: #38715a; } hr { border: 0; border-top: 1px solid #bfcbbf; }
.nightMode.card { background: #202b26; color: #e4eee7; }
.nightMode a { color: #a3d3b5; }
"""
MODEL = genanki.Model(
    1860149783,
    "Birddeck v1",
    fields=[{"name": n} for n in ("Identity", "Question", "Answer", "Source")],
    templates=[
        {
            "name": "Bird",
            "qfmt": "{{Question}}",
            "afmt": '{{FrontSide}}<hr id="answer">{{Answer}}<div class="source">{{Source}}</div>',
        }
    ],
    css=CSS,
)
PROMPTS = {
    "en": {
        "image-name": "Which bird is this?",
        "name-image": "What does this bird look like?",
        "audio-name": "Which bird can you hear?",
        "name-audio": "Recall this bird's voice.",
    },
    "ro": {
        "image-name": "Ce pasăre este?",
        "name-image": "Cum arată această pasăre?",
        "audio-name": "Ce pasăre se aude?",
        "name-audio": "Amintește-ți glasul acestei păsări.",
    },
}


def identity(area, lang, month):
    return json.dumps([area.params(), lang, month], sort_keys=True)


def make_note(species, media, path, card_type, scope, lang):
    esc = html.escape
    name = (
        f"<b>{esc(species.common_name)}</b>"
        f'<div class="scientific">{esc(species.scientific_name)}</div>'
    )
    # Neutral filenames and no species name in image alt text: no answer on the front.
    asset = f'<img src="{path.name}">' if media.kind == "image" else f"[sound:{path.name}]"
    front, back = (name, asset) if card_type.startswith("name-") else (asset, name)
    question = f"<p>{PROMPTS[lang][card_type]}</p>{front}"
    source = (
        f'{esc(media.attribution)} · <a href="{esc(media.license_url)}">'
        f"{esc(media.license.upper())}</a><br>"
        f'<a href="{esc(media.source)}">iNaturalist</a>'
    )
    note_id = f"{scope}:{species.id}:{card_type}"
    return genanki.Note(
        model=MODEL,
        fields=[esc(note_id), question, back, source],
        guid=genanki.guid_for("birddeck-v1", note_id),
        tags=["birddeck", f"inat::{species.id}", card_type, lang],
    )


def build(
    client,
    area,
    output,
    *,
    limit=20,
    lang="en",
    cards=(),
    month=None,
    license_policy="personal",
    progress=lambda message: None,
):
    output = Path(output)
    manifest_path = output.with_suffix(".manifest.json")
    if output.exists() or manifest_path.exists():
        raise BirddeckError(f"Output already exists / Fișierul există deja: {output}")
    scope = identity(area, lang, month)
    deck_id = int(hashlib.sha256(scope.encode()).hexdigest()[:8], 16) % (2**30) + 2**30
    deck = genanki.Deck(deck_id, f"Birddeck :: {area.label} :: {lang} :: {month or 'all'}")
    species_list = client.species(area, limit, lang, month)
    if not species_list:
        raise BirddeckError("No observations in this area / Nu există observații în această zonă.")
    report = {
        "version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "area": asdict(area),
        "language": lang,
        "month": month,
        "ranking": "iNaturalist research-grade wild observations; all years",
        "media_scope": "global exemplars; recordings may contain calls or background species",
        "license_policy": license_policy,
        "requested_species": limit,
        "requested_cards": list(cards),
        "species": [],
        "cards_created": 0,
    }
    paths = set()
    for index, species in enumerate(species_list, 1):
        progress(f"[{index}/{len(species_list)}] {species.common_name} ({species.scientific_name})")
        row = {
            "taxon_id": species.id,
            "name": species.common_name,
            "scientific_name": species.scientific_name,
            "observations": species.count,
            "media": {},
            "missing": {},
            "cards": [],
        }
        for kind in ("image", "audio"):
            selected = [c for c in cards if kind in c]
            if not selected:
                continue
            last_error = "No usable licensed media / Niciun fișier utilizabil cu licență permisă"
            chosen = None
            try:
                for attempt, media in enumerate(client.candidates(species, kind, license_policy)):
                    if attempt >= 5:
                        break
                    try:
                        path = client.download(media)
                    except BirddeckError as exc:
                        last_error = str(exc)
                        continue
                    chosen = (media, path)
                    break
            except BirddeckError as exc:
                last_error = str(exc)
            if chosen is None:
                row["missing"][kind] = last_error
                progress(f"  {'Omis' if lang == 'ro' else 'Skipped'} {kind}: {last_error}")
                continue
            media, path = chosen
            paths.add(str(path))
            row["media"][kind] = dict(asdict(media), filename=path.name)
            for card_type in selected:
                deck.add_note(make_note(species, media, path, card_type, scope, lang))
                row["cards"].append(card_type)
                report["cards_created"] += 1
        report["species"].append(row)
    if not deck.notes:
        reasons = "; ".join(sorted({v for s in report["species"] for v in s["missing"].values()}))
        raise BirddeckError(f"No cards created / Nu s-au creat cartonașe. {reasons}")
    output.parent.mkdir(parents=True, exist_ok=True)
    # Build beside the destination so replacing the completed archive is atomic.
    with tempfile.TemporaryDirectory(prefix=".birddeck-", dir=output.parent) as temp:
        package_path = Path(temp) / "deck.apkg"
        manifest_temp = Path(temp) / "manifest.json"
        package = genanki.Package(deck)
        package.media_files = sorted(paths)
        package.write_to_file(str(package_path))
        manifest_temp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        package_path.replace(output)
        manifest_temp.replace(manifest_path)
    return report
