# MORPC Geographic Identifiers (GEOIDFQ)

How MORPC identifies geographies, modeled on the Census Bureau's fully qualified GEOID. Definitions for every sumlevel are in [`sumlevel-descriptions.json`](sumlevel-descriptions.json). The hierarchy is drawn in [`wof-geographic-hierarchy.drawio`](wof-geographic-hierarchy.drawio).

> **Status:** Census sumlevels in `output_data/` already follow this system. Most MORPC (`M`) sumlevels do not yet; their examples below show the target format, not current output.

## Structure

```
{SUMLEVEL:3}{VARIANT:2}{GEOCOMP:2}US{GEOID}
```

| Part | Width | Meaning | Franklin County, OH: `0500000US39049` |
|---|---|---|---|
| `SUMLEVEL` | 3 | Type of geography | `050` county |
| `VARIANT` | 2 | Which version of the boundaries | `00` default |
| `GEOCOMP` | 2 | Which subset of the entity | `00` total |
| `US` | 2 | Literal separator | `US` |
| `GEOID` | varies | Codes that identify the entity, from largest to smallest | `39` Ohio + `049` Franklin |

This is the Census structure: "050" is the summary level, "0000" is "the 2-digit geographic variant and the 2-digit geographic component," "US" represents the United States, and the rest are FIPS codes.<sup>[1]</sup> Each sumlevel's `geoidfq_format` spells out its GEOID part, for example `{STATE:2}{COUNTY:3}` for `050`.

**Rules**
- Every part is fixed width and zero-padded. Strings can be compared, sorted and sliced by position.
- Census sumlevels are three digits (`050`). MORPC sumlevels are `M` + two digits (`M10`), so they can never collide with Census codes.
- In `geoidfq_format`, a `/` means "either/or." `M10` uses `{COUSUB:5}{PLACEREM:5}` for township remainders, or `{PLACE:5}` padded with zeros for cities and villages.

## Sumlevels

A sumlevel is a type of geography. Each entry in `sumlevel-descriptions.json` gives its names, ID and name fields, Census API names (Census sumlevels only), `geoidfq_format`, variants and Who's On First placetype.

| SL | Name | Authority | Example GEOIDFQ |
|---|---|---|---|
| `040` | STATE | census | `0400000US39` Ohio |
| `050` | COUNTY | census | `0500000US39049` Franklin County |
| `140` | TRACT | census | `1400000US39041010100` tract 101, Delaware County |
| `150` | BLKGRP | census | `1500000US390410101001` block group 1 of that tract |
| `100` | BLOCK | census | `1000000US390410101001000` block 1000 of that block group |
| `160` | PLACE | census | `1600000US3918000` Columbus |
| `155` | PLACE-COUNTY | census | `1550000US3918000049` Columbus, Franklin County part |
| `060` | COUSUB | census | `0600000US3904906922` Blendon Township |
| `070` | TOWNSHIP-REMAINDER | census | `0700000US390490692299999` Blendon Township outside any place |
| `M10` | JURIS | morpc | `M100000US391800000000000` Columbus *(target)* |
| `M10` | JURIS | morpc | `M100000US390490692299999` Blendon Township remainder |
| `M11` | JURIS-COUNTY | morpc | `M110000US391800004900000` Columbus, Franklin County part *(target)* |
| `M60` | PARCEL | morpc | `M600000US39049000000010010416` Franklin parcel `010-010416` *(target)* |

**Parcel IDs (`M60`)** are the auditor's parcel number with punctuation removed, left-padded with zeros to 15 characters, and prefixed with the county FIPS code. Parcel numbers are unique only within a county.

## Hierarchy

Sumlevels relate in four ways. The line styles below are those used in the diagram.

| Relationship | Meaning | Example | Diagram |
|---|---|---|---|
| **Subsidiary** | Child nests in the parent; the child's GEOID contains the parent's codes | COUNTY `39049` → TRACT `39049…` | black arrow |
| **Required for Census query** | Subsidiary, and the Census API needs the parent to query the child | tracts require `in=state:39 county:049` | red arrow |
| **Either/or** | GEOID copies one of two sources | JURIS from PLACE *or* TOWNSHIP-REMAINDER | purple arrow |
| **Made of, not subsidiary** | Parent is built from whole children, but the children's GEOIDs don't include the parent | COUNTY-REGION (`M01`) made of counties | dashed arrow |

**Main chains**

```
US ─ STATE ─ COUNTY ─ TRACT ─ BLKGRP ─ BLOCK
             COUNTY ─ COUSUB ─ TOWNSHIP-REMAINDER ─┬─ JURIS
     STATE ─ PLACE ─────────────────────────────────┘
     STATE ─ PLACE ─ PLACE-COUNTY ─ JURIS-COUNTY  (also from TOWNSHIP-REMAINDER)
     STATE ─ TAZ ─ MAZ ─ GRIDMAZ
     STATE ─ GRIDMILE ─ GRIDQRTM ─ GRIDMAZ
             COUNTY ─ PARCEL ─ BUILD ─ ADDR ─ UNIT
```

**Standalone districts.** These nest in a state but cut across counties and places: CONGRESS, STATESENATE, STATEHOUSE, school districts (ELSD, SCSD, UNSD), PUMA, LIBRARYD, CAMPUS and REFUSED. ZCTA, URBANAREA and MSA sit directly under US.

**Regions.** Rather than one sumlevel per region, regions use two sumlevels: `M01` for regions built from whole counties, and `M02` for regions built from JURIS-COUNTY parts. The region code (`{COUNTYREGION:2}`, `{JURISREGION:2}`) tells regions apart.

The Census publishes the same idea as hierarchy diagrams.<sup>[3]</sup>

## Variants

A variant identifies "a version of a geographic entity based on the date that the entity's boundaries are intended to represent."<sup>[2]</sup> Use a variant when the same sumlevel has more than one boundary set in use.

| Code | Sumlevel | Meaning | Example |
|---|---|---|---|
| `00` | most | Default: boundaries are updated yearly, so the data year sets the vintage | `0500000US39049` |
| `19` | `500` | 119th Congress (add 100 to the code) | `5001900US3903` Ohio District 3 |
| `U9` / `L9` | `610` / `620` | State legislative districts, election in 2023 or 2024 | `610U900US39016` Ohio Senate District 16 |
| `M7` | `310` | OMB Bulletin 23-01, July 21, 2023 | `310M700US18140` Columbus MSA |
| `C2` | `400` | 2020 urban-rural classification | |
| `Z2` / `P2` | `860` / `795` | 2020 ZCTA / PUMA delineation | |

**Rules from the Census**<sup>[2]</sup>
- Child sumlevels use the same variant as their parent from the same period.
- Parent sumlevels don't need a variant. A state has no congressional variant.

**In the JSON.** Each sumlevel has `current_variant` and a `variants` lookup of every documented code. All MORPC sumlevels currently use `00`. To add one, add a code to that sumlevel's `variants` with a `description` and `effective_date`, then update `current_variant`.

## Geographic Components (GEOCOMP)

A geographic component "is a subset of a given type of geographic entity based on a certain geographic or population characteristic."<sup>[4]</sup> The GEOID part stays the same.

| GEOIDFQ | Meaning |
|---|---|
| `0400000US39` | Ohio, total |
| `040C201US39` | Ohio, urban portion (2020 classification) |
| `050C243US39049` | Franklin County, rural portion |

From the 2020 classification on, urban (`01`) and rural (`43`) components use the urban-rural vintage as their variant, which is why the examples carry `C2`.<sup>[2]</sup>

**In the JSON.** `geocomps` lists the 37 current Census codes and their descriptions.<sup>[4]</sup> Only Census geocomps are used. Census produces components "for a limited set of summary levels," so not every code applies to every sumlevel.<sup>[4]</sup>

## Sources

1. U.S. Census Bureau, [Understanding Geographic Identifiers (GEOIDs)](https://www.census.gov/programs-surveys/geography/guidance/geo-identifiers.html)
2. U.S. Census Bureau, [Geographic Variant Codes and Definitions](https://www.census.gov/programs-surveys/geography/guidance/geo-variants.html)
3. U.S. Census Bureau, [Hierarchy Diagrams](https://www.census.gov/programs-surveys/geography/guidance/hierarchy.html)
4. U.S. Census Bureau, [2020 Census Demographic and Housing Characteristics File (DHC) Technical Documentation](https://www.census.gov/programs-surveys/decennial-census/technical-documentation/complete-technical-documents.html), 2023, Appendix A, p. A-24; data dictionary, pp. 3-17 to 3-18
