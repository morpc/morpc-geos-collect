# morpc-geos-collect
Collect a set of geographies of interest to MORPC from various sources and create a lookup table that contains the identifiers for the geographies.

## Outputs

Running `morpc-geos-collect.ipynb` produces, in `output_data/`:
  - `morpc-geos.gpkg` -- a geopackage with one layer per collected geography.
  - `morpc-geos-<LAYER>.resource.yaml` and `.schema.yaml` -- a Frictionless resource and schema for each layer of the geopackage. Layers with identical schemas share a single schema file.
  - `morpc-geos.package.yaml` -- a Frictionless data package bundling all of the geopackage layer resources.
  - `morpc-geos-lookup.csv` -- a lookup table of identifiers for the collected geographies, with its own resource (`morpc-geos-lookup.resource.yaml`) and schema (`morpc-geos-lookup.schema.yaml`).

## Release workflow

`morpc-geos.gpkg` is too large for Git (even with Git LFS) to hold economically, so it is not committed to this repository. Instead it is distributed as a GitHub release asset, and every resource descriptor above (the geopackage layers and the lookup table) points at that release's asset URLs.

The notebook's "Prepare release" section handles this in two steps:
  1. **Prepare** -- `morpc.frictionless.prepare_release()` rewrites each resource descriptor's `path` to the release asset URL it will have once published (keeping the local file recorded under `_cache` so the descriptor still resolves locally), and rebuilds `morpc-geos.package.yaml`. This step runs automatically and only touches files on disk.
  2. **Publish** -- actually creating the GitHub release (`morpc.frictionless.create_release()`, which runs `gh release create` and uploads the geopackage, all resource/schema files, and the package descriptor as release assets) is gated behind a `CREATE_RELEASE` flag in the notebook and must be set to `True` and run manually, since it is externally visible and can only be done once per release tag.

Release tags follow CalVer (`vYYYY.M.D`, via `morpc.frictionless.calver()`). See the release history at https://github.com/morpc/morpc-geos-collect/releases.
