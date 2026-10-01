# Plan: MORPC Geographies Spatial Database

A PostGIS database with one table per sumlevel, each holding real geometries and GEOIDFQs that follow [`geoidfq.md`](geoidfq.md). Sumlevel definitions come from [`sumlevel-descriptions.json`](sumlevel-descriptions.json).

**Scope:** all 39 sumlevels, built in phases. Each table holds the **current** version only (`current_variant`); earlier versions live in earlier releases.

## Design

### Schema

| Object | Purpose |
|---|---|
| `geos.sumlevel` | One row per sumlevel, loaded from `sumlevel-descriptions.json` |
| `geos.variant` | One row per (sumlevel, variant code) |
| `geos.geocomp` | The 37 current Census geocomp codes |
| `geos.<name>` | One table per sumlevel, named from `hierarchy_string` in lower case with `-` → `_` (e.g. `geos.juris_county`) |
| `geos.region_member` | Membership for "made of" sumlevels: which counties form an M01 region, which JURIS-COUNTY parts form an M02 region |
| `geos.lookup` (view) | `UNION ALL` of `geoidfq`, `sumlevel`, `name` across all tables, replacing `morpc-geos-lookup.csv` |

### Columns in every sumlevel table

| Column | Type | Notes |
|---|---|---|
| `geoidfq` | `text` primary key | Built from `geoidfq_format` |
| `geoid` | `text` | The part after `US` |
| `sumlevel`, `variant`, `geocomp` | `text` | Foreign keys to the registry tables; `geocomp` is `00` |
| code columns | `text` | One per placeholder in the format (`statefp`, `countyfp`, `taz`, …) |
| `name` | `text` | From `nameField`, where one exists |
| `legacy_id` | `text` | From `legacyIdField` (TAZ, MAZ, GRIDMAZ only) |
| `parent_geoidfq` | `text` | Foreign key to the parent table for **subsidiary** edges only |
| `source`, `source_version`, `loaded_at` | | Which repo or release the row came from |
| `geom` | `geometry(MultiPolygon, 3735)` | `Point` for ADDR; GIST index |

- **GEOIDFQ construction:** done by one function that reads `geoidfq_format`, so the JSON stays the single source of truth. The same function gives a regex for checking.
- **Relationship edges:**
  - **Subsidiary** edges get a foreign key.
  - **"Made of"** edges (M01, M02, BLOB) use `geos.region_member`-style tables, not foreign keys.
  - **Either/or** edges (JURIS from PLACE or TOWNSHIP-REMAINDER) store whichever source was used.
- **CRS:** EPSG:3735, the same as the current GeoPackage. Sibling repos publish in 4326 and get reprojected on load.

### Loading

- **Python loader:** a loader in this repo reads each input through its Frictionless resource, builds the GEOIDFQs, reprojects, validates, and writes with `GeoDataFrame.to_postgis`.
- **Runs alongside the GeoPackage:** the loader runs after the existing collection steps, so the GeoPackage release keeps working until the database replaces it.
- **Rebuilds:** loads are full rebuilds per table: write to a staging table, run QA, then swap it in inside a transaction.

## QA (run for every table, every load)

| Check | Pass condition |
|---|---|
| Key | `geoidfq` unique and not null |
| Format | Every `geoidfq` matches the sumlevel's format regex, variant = `current_variant` |
| Parent | Every `parent_geoidfq` exists |
| Geometry | `ST_IsValid`, not empty, correct type and SRID |
| Nesting | Child area outside its parent is below a tolerance (TAZs have known slivers; see PR #3) |
| Count | Row count matches the source, with any dropped rows logged |

## Phases

Each step ends with the QA table above passing for the tables it creates.

### Phase 0 — Infrastructure
1. Stand up PostGIS. Use `docker compose` for development; production hosting is to be decided. Create the `geos` schema plus read-only and loader roles.
2. Load `geos.sumlevel`, `geos.variant` and `geos.geocomp` from the JSON. **Verify:** 39 sumlevels and 37 geocomps.
3. Build the GEOIDFQ function and format regexes. **Verify:** every example in `geoidfq.md` round-trips.

### Phase 1 — Census sumlevels (22)
| Status | Sumlevels | Source |
|---|---|---|
| Already collected | 050, 060, 070, 100, 140, 150, 155, 160, 310, 400, 860, 970 | `morpc-censustiger-standardize` |
| Not collected yet | 010, 020, 030, 040, 500, 610, 620, 795, 950, 960 | `morpc-censustiger-standardize` if it publishes them (not checked; the repo isn't cloned here), otherwise TIGERweb |

- **Fix while loading:** 400 and 860 GEOIDFQs must use `C2`/`Z2`, not `00`.
- **950 and 960:** Ohio has no elementary or secondary districts, so these tables are created empty.

### Phase 2 — MORPC sumlevels with sources in this repo
| Sumlevel | Work |
|---|---|
| M10 JURIS, M11 JURIS-COUNTY | Rebuild GEOIDFQs in the new formats (place or township-remainder branch) |
| M01, M02 regions | Merge the separate `REGION*` layers into two tables, assign 2-digit region codes, fill `geos.region_member` |
| M20 TAZ, M21 MAZ, M22 GRIDMAZ | Number within parent (sorted by legacy ID), keep `TAZ2020`/`MAZ2020`/`GridMAZ20` as `legacy_id`; use the TAZ's county for the 52 MAZs whose county disagrees; resolve the ~60–77 rows with null TAZ/MAZ |
| M31 LIBRARYD | Franklin County only today; other counties need a source |

### Phase 3 — MORPC sumlevels from sibling repos
| Sumlevel | Source | Main issue |
|---|---|---|
| M60 PARCEL | `morpc-parcels-standardize` (1.1M polygons) | Delaware has no parcel IDs; duplicate IDs within some counties; ID becomes county FIPS + 15-char padded parcel number |
| M61 BUILD | `morpc-bingbuildings-standardize` or `morpc-osmbuildings-standardize` | Choose one source; assign each building to a parcel by spatial join; buildings that cross parcels |
| M62 ADDR | `morpc-addresspoints-standardize` (1.25M points) | Assign each point to a building and parcel |
| M63 UNIT | Address points' `unitnum`/`unittype` | Units have no geometry of their own; use the address point or no geometry |
| M32 CAMPUS | `morpc-campushousing-standardize` (`campuses-parcels` or `campuses-osm`) | Pick the boundary source |
| M50 BLOB | `morpc-gq-standardize` (686 group-quarters blobs) | Only GQ blobs exist; other blob types later |

### Phase 4 — Sumlevels without a source
| Sumlevel | What's needed |
|---|---|
| M30 REFUSED | A boundary source, and a new code (M30 clashes with morpc-py's REGIONSWACO) |
| M40 GRIDMILE, M41 GRIDQRTM | Generate the grids, and decide how GRIDMAZ's `GRID_ID` maps to them |

### Phase 5 — Integration
1. `geos.lookup` view and parent–child relationship view. **Verify:** the view's row count equals the sum of the table row counts.
2. Point the notebook's outputs at the database, then decide whether to keep publishing the GeoPackage.
3. Document connection details, roles and refresh steps in the README.

## Decisions needed

1. **Hosting:** a MORPC server, a cloud provider, or local only? This also decides backups and who can connect.
2. **Extent:** keep only entities that intersect the 15-county region (unclipped), or all of Ohio? US, region and division tables hold one row each either way.
3. **`-MORPC` layers:** the current output has COUNTY-MORPC, JURIS-MORPC, JURIS-COUNTY-MORPC, REGIONMPO-MORPC and REGIONTDM-MORPC (morpc-py M23–M27). They aren't among the 39 sumlevels. Drop them, or keep them as an alternative `source` for COUNTY/JURIS rows?
4. **CRS:** EPSG:3735 (Ohio South) matches current outputs. The region's northern counties may fall in the Ohio North zone (EPSG:3734), so check how much distortion that causes before settling on 3735, or store in 4326.
5. **Building source:** Bing (1.06M footprints) or OSM (367K, with attributes)?
6. **Where the JSON lives:** keep `sumlevel-descriptions.json` here, or move it into morpc-py so the loader and morpc-census share it.
