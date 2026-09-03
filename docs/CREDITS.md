# Credits & third-party licenses

greyline itself is licensed **GPL-2.0-or-later** (see [`LICENSE`](../LICENSE)). It
bundles the following third-party data and assets under their own terms.

## Natural Earth — map data (public domain)

The default vector map is drawn from Natural Earth data in `worldtime/geodata/`:

- `ne_110m_land.geojson`
- `ne_110m_admin_0_countries.geojson`
- `ne_10m_time_zones.geojson`
- `ne_10m_geographic_lines.geojson`

Natural Earth is in the **public domain**. No permission is needed to use it.
Terms: <https://www.naturalearthdata.com/about/terms-of-use/>

The bundled copies are **not byte-for-byte upstream**. `tools/prep_geodata.py` strips
the properties greyline never reads (fifteen per timezone feature, of which it uses
one) and rounds coordinates to 3 decimal places — about 110 m, a hundredth of a pixel
at 4K. That takes the bundle from 4.57 MB to 2.91 MB, and the browser demo's first
paint from 1.57 MB to 0.87 MB gzipped. The script's docstring records the reasoning
and `python tools/prep_geodata.py --check` verifies the shipped files match it.

## Tux — default corner logo (Larry Ewing)

`worldtime/assets/tux.png` is Tux, the Linux mascot, created by **Larry Ewing**
(`lewing@isc.tamu.edu`) using **GIMP**.

> Permission to use and/or modify this image is granted provided you acknowledge
> me (`lewing@isc.tamu.edu`) and The GIMP if someone asks.

Source: <https://commons.wikimedia.org/wiki/File:Linux_mascot_tux.png>

## City calibration data — Maxim Proskurnya (GPL)

The city coordinates/offsets used to calibrate the map projection were derived from
Maxim Proskurnya's **GPL** "World Time Wallpaper" (v2.4.x), © 2006–2011
(`axofiber at gmail.com`). See `reference/`.

## Not bundled: IBM/Lenovo ThinkPad artwork

The raster ThinkPad map and the IBM/ThinkPad wordmark are copyright IBM/Lenovo and
are **not** included in this repository. See [`NOTICE`](../NOTICE) for how to supply
your own if you want the `raster` map style or the original logo.

## Development

This project was built with the assistance of AI coding tools.
