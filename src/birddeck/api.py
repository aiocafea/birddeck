import hashlib
import json
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .domain import FREE_LICENSES, PERSONAL_LICENSES, BirddeckError, Media, Species

API = "https://api.inaturalist.org/v1"
MAX_MEDIA_BYTES = 20 * 1024 * 1024
EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/mp4": ".m4a",
    "audio/x-m4a": ".m4a",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/ogg": ".ogg",
    "application/ogg": ".ogg",
    "audio/flac": ".flac",
}


def allowed_url(url):
    host = urlparse(url).hostname or ""
    return urlparse(url).scheme == "https" and (
        host in {"inaturalist-open-data.s3.amazonaws.com", "static.inaturalist.org"}
        or host.endswith(".inaturalist.org")
    )


class Client:
    def __init__(self, cache: Path, refresh=False):
        self.cache = cache
        self.cache.mkdir(parents=True, exist_ok=True)
        self.refresh = refresh
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "birddeck/0.1 (https://github.com/aiocafea/birddeck)"
        retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
        self.session.mount("https://", HTTPAdapter(max_retries=retry))
        self.last_request = 0.0

    def close(self):
        self.session.close()

    def get(self, endpoint, **params):
        key = hashlib.sha256(json.dumps([endpoint, params], sort_keys=True).encode()).hexdigest()
        path = self.cache / f"{key}.json"
        if not self.refresh and path.exists() and time.time() - path.stat().st_mtime < 86400:
            try:
                return json.loads(path.read_text())
            except (ValueError, OSError):
                pass
        # Stay below iNaturalist's requested 60 API calls/minute.
        time.sleep(max(0, 1.1 - (time.monotonic() - self.last_request)))
        self.last_request = time.monotonic()
        try:
            with self.session.get(f"{API}/{endpoint}", params=params, timeout=(10, 45)) as r:
                r.raise_for_status()
                data = r.json()
            if not isinstance(data, dict) or not isinstance(data.get("results"), list):
                raise ValueError("Invalid API response")
        except (requests.RequestException, ValueError) as exc:
            raise BirddeckError(f"iNaturalist: {exc}") from exc
        path.write_text(json.dumps(data), encoding="utf-8")
        return data

    def places(self, query):
        return self.get("places/autocomplete", q=query, per_page=8)["results"]

    def species(self, area, limit, lang, month=None):
        params = dict(
            area.params(),
            taxon_id=3,
            quality_grade="research",
            captive="false",
            per_page=limit,
            locale=lang,
        )
        if month:
            params["month"] = month
        rows = self.get("observations/species_counts", **params)["results"]
        result = []
        for row in rows:
            taxon = row["taxon"]
            if taxon.get("rank") != "species":
                continue
            result.append(
                Species(
                    taxon["id"],
                    taxon["name"],
                    taxon.get("preferred_common_name")
                    or taxon.get("english_common_name")
                    or taxon["name"],
                    row["count"],
                    taxon.get("default_photo"),
                )
            )
        return sorted(result, key=lambda s: (-s.count, s.id))[:limit]

    def candidates(self, species, kind, license_policy):
        allowed = FREE_LICENSES if license_policy == "free" else PERSONAL_LICENSES

        def convert(item, source):
            license_code = item.get("license_code")
            if license_code not in allowed or item.get("hidden"):
                return None
            if kind == "image":
                url = item.get("medium_url") or item.get("url", "").replace("/square.", "/medium.")
            else:
                url = item.get("file_url", "")
            if not allowed_url(url):
                return None
            return Media(
                url,
                source,
                item.get("attribution") or "iNaturalist contributor",
                license_code,
                kind,
            )

        seen = set()
        if kind == "image" and species.photo:
            media = convert(
                species.photo, f"https://www.inaturalist.org/photos/{species.photo['id']}"
            )
            if media:
                seen.add(media.url)
                yield media
        params = {
            "taxon_id": species.id,
            "quality_grade": "research",
            "captive": "false",
            "per_page": 30,
            "order_by": "votes",
            "order": "desc",
        }
        params["photos" if kind == "image" else "sounds"] = "true"
        # Media exemplars can come from anywhere; only the species ranking is local.
        for obs in self.get("observations", **params)["results"]:
            taxon = obs.get("taxon") or {}
            if species.id not in [taxon.get("id"), *taxon.get("ancestor_ids", [])]:
                continue
            for item in obs.get("photos" if kind == "image" else "sounds", []):
                source = (
                    f"https://www.inaturalist.org/photos/{item['id']}"
                    if kind == "image"
                    else f"https://www.inaturalist.org/observations/{obs['id']}"
                )
                media = convert(item, source)
                if media and media.url not in seen:
                    seen.add(media.url)
                    yield media

    def download(self, media):
        if not allowed_url(media.url):
            raise BirddeckError("Unsupported media host")
        key = hashlib.sha256(media.url.encode()).hexdigest()
        for ext in set(EXTENSIONS.values()):
            cached = self.cache / f"birddeck_{key}{ext}"
            if not self.refresh and cached.exists() and cached.stat().st_size:
                return cached
        try:
            with self.session.get(
                media.url, stream=True, timeout=(10, 45), allow_redirects=False
            ) as r:
                r.raise_for_status()
                if r.is_redirect:
                    raise BirddeckError("Media redirect refused")
                mime = r.headers.get("Content-Type", "").split(";")[0].strip().lower()
                ext = EXTENSIONS.get(mime)
                valid_kind = mime.startswith(media.kind + "/") or (
                    media.kind == "audio" and mime == "application/ogg"
                )
                if not ext or not valid_kind:
                    raise BirddeckError(f"Unsupported media type: {mime}")
                if int(r.headers.get("Content-Length", 0)) > MAX_MEDIA_BYTES:
                    raise BirddeckError("Media exceeds 20 MiB")
                content = bytearray()
                for chunk in r.iter_content(65536):
                    content.extend(chunk)
                    if len(content) > MAX_MEDIA_BYTES:
                        raise BirddeckError("Media exceeds 20 MiB")
                if not content:
                    raise BirddeckError("Empty media response")
            path = self.cache / f"birddeck_{key}{ext}"
            temp = path.with_suffix(".part")
            temp.write_bytes(content)
            temp.replace(path)
            return path
        except (requests.RequestException, ValueError) as exc:
            raise BirddeckError(f"Media: {exc}") from exc
