import json
import sqlite3
import zipfile

import pytest

from birddeck.deck import build
from birddeck.domain import CARD_TYPES, Area, BirddeckError, Media, Species


class FakeClient:
    def __init__(self, tmp_path, audio=True):
        self.tmp = tmp_path
        self.audio = audio

    def species(self, *args):
        return [Species(12727, "Turdus migratorius", "Robin <script>", 42)]

    def candidates(self, species, kind, policy):
        if kind == "audio" and not self.audio:
            return
        yield Media(
            "https://static.inaturalist.org/example",
            "https://example.org/source",
            'Someone <b> & "friend"',
            "cc-by",
            kind,
        )

    def download(self, media):
        path = self.tmp / ("birddeck_abc.jpg" if media.kind == "image" else "birddeck_def.mp3")
        path.write_bytes(b"test asset")
        return path


def unpack(path, tmp_path):
    with zipfile.ZipFile(path) as z:
        manifest = json.loads(z.read("media"))
        for archive_name in manifest:
            assert z.read(archive_name) == b"test asset"
        db = tmp_path / (path.stem + ".sqlite")
        db.write_bytes(z.read("collection.anki2"))
    with sqlite3.connect(db) as con:
        notes = con.execute("select guid, flds from notes order by guid").fetchall()
        cards = con.execute("select count(*) from cards").fetchone()[0]
    return notes, cards, manifest


def test_all_directions_embed_media_and_escape_remote_text(tmp_path):
    target = tmp_path / "birds.apkg"
    report = build(
        FakeClient(tmp_path), Area("Test", place_id=1), target, cards=CARD_TYPES, lang="ro"
    )
    notes, cards, media = unpack(target, tmp_path)
    assert cards == report["cards_created"] == 4
    assert len(media) == 2
    questions = [fields.split("\x1f")[1] for _, fields in notes]
    assert sum("Robin" in q for q in questions) == 2
    assert sum("[sound:" in q for q in questions) == 1
    assert sum("<img" in q for q in questions) == 1
    assert all("<script>" not in fields for _, fields in notes)
    assert all("Someone &lt;b&gt;" in fields for _, fields in notes)
    assert "Ce pasăre" in " ".join(questions)
    assert json.loads(target.with_suffix(".manifest.json").read_text())["area"]["place_id"] == 1


def test_missing_sound_never_creates_empty_cards(tmp_path):
    target = tmp_path / "birds.apkg"
    report = build(
        FakeClient(tmp_path, audio=False), Area("Test", place_id=1), target, cards=CARD_TYPES
    )
    assert report["cards_created"] == 2
    assert "audio" in report["species"][0]["missing"]
    assert unpack(target, tmp_path)[1] == 2


def test_no_media_does_not_leave_an_empty_package(tmp_path):
    target = tmp_path / "birds.apkg"
    with pytest.raises(BirddeckError, match="No cards"):
        build(
            FakeClient(tmp_path, audio=False),
            Area("Test", place_id=1),
            target,
            cards=("audio-name",),
        )
    assert not target.exists()


def test_regeneration_keeps_note_ids(tmp_path):
    client = FakeClient(tmp_path)
    for name in ("a", "b"):
        build(client, Area("Test", place_id=1), tmp_path / f"{name}.apkg", cards=CARD_TYPES)
    a = unpack(tmp_path / "a.apkg", tmp_path)[0]
    b = unpack(tmp_path / "b.apkg", tmp_path)[0]
    assert [n[0] for n in a] == [n[0] for n in b]


def test_existing_output_is_preserved(tmp_path):
    target = tmp_path / "birds.apkg"
    target.write_bytes(b"existing deck")
    with pytest.raises(BirddeckError, match="already exists"):
        build(FakeClient(tmp_path), Area("Test", place_id=1), target, cards=CARD_TYPES)
    assert target.read_bytes() == b"existing deck"
