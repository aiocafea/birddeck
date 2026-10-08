from unittest.mock import Mock

import pytest

from birddeck.cli import TEXT, main, parser, resolve_area
from birddeck.domain import BirddeckError


@pytest.mark.parametrize("position", ["before", "after"])
def test_language_option_on_either_side_of_subcommand(position):
    argv = (
        ["--lang", "ro", "places", "Bucharest"]
        if position == "before"
        else ["places", "Bucharest", "--lang", "ro"]
    )
    assert parser("ro").parse_args(argv).lang == "ro"


def test_ambiguous_location_is_not_silently_selected(monkeypatch, capsys):
    client = Mock()
    client.places.return_value = [
        {"id": 1, "display_name": "Springfield A"},
        {"id": 2, "display_name": "Springfield B"},
    ]
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    args = parser("en").parse_args(["build", "--location", "Springfield", "--output", "x.apkg"])
    with pytest.raises(BirddeckError, match="Several places"):
        resolve_area(args, client, TEXT["en"])
    assert "Springfield B" in capsys.readouterr().out


def test_invalid_card_types_fail_before_network(monkeypatch, tmp_path):
    client = Mock()
    monkeypatch.setattr("birddeck.cli.Client", client)
    result = main(
        ["build", "--place", "1", "--cards", "unknown", "--output", str(tmp_path / "x.apkg")]
    )
    assert result == 1
    client.assert_not_called()


def test_radius_cannot_be_silently_ignored():
    args = parser("en").parse_args(
        ["build", "--place", "1", "--radius", "10", "--output", "x.apkg"]
    )
    with pytest.raises(BirddeckError):
        resolve_area(args, Mock(), TEXT["en"])
