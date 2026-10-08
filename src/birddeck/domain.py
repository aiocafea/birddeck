import math
from dataclasses import dataclass

CARD_TYPES = ("image-name", "name-image", "audio-name", "name-audio")
FREE_LICENSES = {"cc0", "cc-by", "cc-by-sa"}
PERSONAL_LICENSES = FREE_LICENSES | {"cc-by-nc", "cc-by-nc-sa", "cc-by-nd", "cc-by-nc-nd"}


class BirddeckError(Exception):
    """An actionable failure that the CLI can print without a traceback."""


@dataclass(frozen=True)
class Area:
    label: str
    place_id: int | None = None
    lat: float | None = None
    lon: float | None = None
    radius: float = 25

    def __post_init__(self):
        if self.place_id is not None:
            if self.place_id < 1 or self.lat is not None or self.lon is not None:
                raise ValueError("Use a positive place ID OR coordinates.")
        elif (
            self.lat is None
            or self.lon is None
            or not math.isfinite(self.lat)
            or not -90 <= self.lat <= 90
            or not math.isfinite(self.lon)
            or not -180 <= self.lon <= 180
            or not math.isfinite(self.radius)
            or not 0 < self.radius <= 500
        ):
            raise ValueError("Latitude: -90..90; longitude: -180..180; radius: >0..500 km.")

    def params(self):
        if self.place_id is not None:
            return {"place_id": self.place_id}
        return {"lat": self.lat, "lng": self.lon, "radius": self.radius}


@dataclass(frozen=True)
class Species:
    id: int
    scientific_name: str
    common_name: str
    count: int
    photo: dict | None = None


@dataclass(frozen=True)
class Media:
    url: str
    source: str
    attribution: str
    license: str
    kind: str

    @property
    def license_url(self):
        if self.license == "cc0":
            return "https://creativecommons.org/publicdomain/zero/1.0/"
        # The API's code does not identify a version; link the license family.
        return f"https://creativecommons.org/licenses/{self.license.removeprefix('cc-')}/"
