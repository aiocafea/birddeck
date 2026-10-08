# A small Bucharest deck

This is a live-run example, not a fixture. Counts and species can change as new observations arrive.

```sh
birddeck build --lat 44.4268 --lon 26.1025 --radius 25 \
  --limit 5 --lang ro --cards all --output bucuresti-5.apkg
```

Run on 8 October 2026:

```text
Zona: 44.4268, 26.1025 / 25 km
Clasament după observațiile iNaturalist, nu după mărimea populațiilor.
[1/5] Rață mare (Anas platyrhynchos)
[2/5] Cioara grivă (Corvus cornix)
[3/5] Porumbel (Columba livia)
[4/5] Lișița (Fulica atra)
[5/5] Mierla (Turdus merula)
Am creat 20 cartonașe pentru 5 specii: bucuresti-5.apkg
Specii cu fișiere lipsă: 0. Detalii: bucuresti-5.manifest.json
```

The package contains five photographs and five recordings, shared between the forward and reverse cards. The export and its source manifest are generated locally and excluded from Git. Each media file retains its contributor's license.
