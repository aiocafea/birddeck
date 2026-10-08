from unittest.mock import Mock

import pytest

from birddeck.api import MAX_MEDIA_BYTES, Client, allowed_url
from birddeck.domain import Area, BirddeckError, Media, Species


@pytest.mark.parametrize(
    "lat,lon,radius",
    [(91, 0, 2), (0, -181, 2), (0, 0, 0), (float("nan"), 0, 2), (0, 0, float("inf"))],
)
def test_invalid_coordinates(lat, lon, radius):
    with pytest.raises(ValueError):
        Area("bad", lat=lat, lon=lon, radius=radius)


def test_coordinates_and_place_are_exclusive():
    with pytest.raises(ValueError):
        Area("bad", place_id=1, lat=40, lon=20)


@pytest.mark.parametrize(
    "url",
    [
        "http://static.inaturalist.org/x",
        "https://localhost/x",
        "https://static.inaturalist.org.evil.com/x",
        "file:///etc/passwd",
    ],
)
def test_media_host_validation(url):
    assert not allowed_url(url)


def test_local_ranking_params_and_name_fallback(tmp_path):
    client = Client(tmp_path)
    client.get = Mock(
        return_value={
            "results": [
                {
                    "count": 9,
                    "taxon": {
                        "id": 1,
                        "name": "Bird one",
                        "rank": "species",
                        "english_common_name": "Fallback",
                    },
                },
                {"count": 15, "taxon": {"id": 2, "name": "Bird two", "rank": "species"}},
            ]
        }
    )
    birds = client.species(Area("circle", lat=44, lon=26, radius=10), 10, "ro", 5)
    assert [b.count for b in birds] == [15, 9]
    assert birds[1].common_name == "Fallback"
    params = client.get.call_args.kwargs
    assert params["lat"] == 44 and params["lng"] == 26 and params["radius"] == 10
    assert params["month"] == 5 and params["captive"] == "false"
    assert params["quality_grade"] == "research"


@pytest.mark.parametrize(
    "policy,license_code,expected",
    [
        ("personal", None, 0),
        ("personal", "cc-by-nc", 1),
        ("free", "cc-by-nc", 0),
        ("free", "cc-by-sa", 1),
    ],
)
def test_each_asset_license_is_checked(tmp_path, policy, license_code, expected):
    client = Client(tmp_path)
    client.get = Mock(
        return_value={
            "results": [
                {
                    "id": 10,
                    "taxon": {"id": 1},
                    "sounds": [
                        {
                            "id": 1,
                            "license_code": license_code,
                            "file_url": "https://static.inaturalist.org/sounds/1.mp3",
                        }
                    ],
                }
            ]
        }
    )
    candidates = list(client.candidates(Species(1, "Bird", "Bird", 1), "audio", policy))
    assert len(candidates) == expected


def response(mime, content):
    r = Mock()
    r.__enter__ = Mock(return_value=r)
    r.__exit__ = Mock(return_value=False)
    r.is_redirect = False
    r.headers = {"Content-Type": mime}
    r.iter_content.return_value = [content]
    return r


@pytest.mark.parametrize(
    "mime,content",
    [("text/html", b"blocked"), ("audio/mpeg", b""), ("audio/mpeg", b"a" * (MAX_MEDIA_BYTES + 1))],
)
def test_invalid_download_never_enters_cache(tmp_path, mime, content):
    client = Client(tmp_path)
    client.session.get = Mock(return_value=response(mime, content))
    with pytest.raises(BirddeckError):
        client.download(
            Media("https://static.inaturalist.org/sounds/a.mp3", "", "", "cc0", "audio")
        )
    assert not list(tmp_path.iterdir())


def test_media_cache_avoids_second_download(tmp_path):
    client = Client(tmp_path)
    client.session.get = Mock(return_value=response("audio/mpeg", b"audio"))
    media = Media("https://static.inaturalist.org/sounds/a.mp3", "", "", "cc0", "audio")
    first = client.download(media)
    assert client.download(media) == first
    client.session.get.assert_called_once()
