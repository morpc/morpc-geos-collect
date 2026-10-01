"""Export doc/sumlevel-descriptions.json from doc/wof-geographic-hierarchy.drawio.

The diagram holds each sumlevel's table fields. This script adds what lives only
in the JSON -- descriptions, the documented variant codes, legacy ID fields and
the Census geographic components -- and writes the file. Re-run it after
editing the diagram:

    python scripts/export_sumlevels.py

The JSON is copied into morpc-geos-model (reference/), which builds its schemas
from it.
"""
import html
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DRAWIO = ROOT / 'doc' / 'wof-geographic-hierarchy.drawio'
OUT = ROOT / 'doc' / 'sumlevel-descriptions.json'

# Output order of each sumlevel's fields. Every name except those added below
# is a row label in the diagram's tables.
FIELD_ORDER = ['singular', 'plural', 'description', 'hierarchy_string', 'authority', 'idField',
               'legacyIdField', 'nameField', 'censusQueryName', 'censusRestAPI_layername',
               'geoidfq_format', 'current_variant', 'variants', 'wof_placetype']

# Descriptions live only in the JSON, not the diagram
DESCRIPTIONS = {
    '010': 'The United States as a whole. The top of the census geographic hierarchy.',
    '020': 'One of the four Census regions (Northeast, Midwest, South, West) that group states for statistical reporting.',
    '030': 'One of the nine Census divisions that subdivide the four Census regions into groups of states.',
    '040': 'A U.S. state or state-equivalent such as the District of Columbia or Puerto Rico.',
    '050': 'A county or county-equivalent, the primary legal subdivision of a state.',
    '060': 'A county subdivision, which in Ohio are townships and the cities and villages that have separated from them. Nests within a county.',
    '070': 'The part of a county subdivision that is either within a given place or outside all places (the remainder), split by county. Used to separate townships from the cities and villages that overlap them.',
    '100': 'A census block, the smallest unit of census geography, bounded by visible features such as streets and streams and by legal boundaries. Nests within a block group.',
    '140': 'A census tract, a small, relatively stable statistical subdivision of a county that typically holds 1,200 to 8,000 people. Nests within a county.',
    '150': 'A block group, a cluster of census blocks within a tract that typically holds 600 to 3,000 people. The smallest geography for most American Community Survey estimates.',
    '155': 'The portion of a place that falls within a given county. Places that cross county lines are split into one part per county.',
    '160': 'A place, meaning an incorporated city or village or a census designated place (CDP). Places can cross county lines.',
    '310': 'A metropolitan or micropolitan statistical area (core-based statistical area), made up of one or more counties around an urban core plus adjacent counties with strong commuting ties.',
    '400': 'An urban area, a densely settled territory delineated by the Census Bureau from housing and population density, independent of political boundaries.',
    '500': 'A district from which a member of the U.S. House of Representatives is elected. Redrawn after each decennial census.',
    '610': 'A state legislative district for the upper chamber, which in Ohio is the Ohio Senate.',
    '620': 'A state legislative district for the lower chamber, which in Ohio is the Ohio House of Representatives.',
    '795': 'A public use microdata area, a statistical area of at least 100,000 people used to publish ACS Public Use Microdata Sample (PUMS) records.',
    '860': 'A ZIP code tabulation area, the Census Bureau\'s generalized areal representation of a five-digit USPS ZIP code, built from census blocks.',
    '950': 'An elementary school district, which serves only the lower grades and is overlaid by a secondary school district.',
    '960': 'A secondary school district, which serves only the upper grades and overlays one or more elementary school districts.',
    '970': 'A unified school district, which serves all grade levels. Most Ohio school districts are unified.',
    'M01': 'A MORPC region made by combining whole counties, such as the 15-county MORPC region. Consolidates the county-based regions that currently each have their own sumlevel.',
    'M02': 'A MORPC region made by combining jurisdiction county parts, for regions whose boundaries follow municipal or township lines rather than county lines.',
    'M10': 'A jurisdiction, the closest representation of municipal and political jurisdictions: whole cities and villages plus the township remainders outside them.',
    'M11': 'A jurisdiction county part, meaning a jurisdiction split by county so that a city or village crossing a county line is represented once per county.',
    'M20': 'A transportation analysis zone (TAZ), the zone system MORPC\'s travel demand model uses to summarize households, population, and employment.',
    'M21': 'A micro analysis zone (MAZ), a finer subdivision of TAZs used by MORPC\'s activity-based travel demand model.',
    'M22': 'The intersection of MAZs with the quarter-mile grid, the smallest zone in MORPC\'s modeling hierarchy.',
    'M30': 'A solid waste (refuse) management district, the county or multi-county district responsible for solid waste planning in Ohio.',
    'M31': 'A library district, the service area of a public library system.',
    'M32': 'A campus, the boundary of a college, university, or similar institutional campus.',
    'M40': 'A cell in a regular one-mile grid covering the region, used to summarize data independently of administrative boundaries.',
    'M41': 'A cell in a regular quarter-mile grid, made by dividing each one-mile grid cell into sixteen.',
    'M50': 'A blob, a geometry derived by filtering or combining block groups, blocks, or parcels. Often used to show the general location of a type of population, and blobs from different sources may coexist in one layer.',
    'M60': 'A parcel, a unit of land as recorded by the county auditor. The ID is the auditor\'s parcel number without punctuation, left-padded with zeros to 15 characters.',
    'M61': 'A building, a structure located on a parcel.',
    'M62': 'An address point, a single street address associated with a building.',
    'M63': 'A unit, such as an apartment or suite, within an address.',
}

# Census variant meanings, from census.gov/programs-surveys/geography/guidance/geo-variants.html
def v(description, effective_date=None):
    return {'description': description, 'effective_date': effective_date}

STANDARD = {'00': v('Default: no geographic variant specified. Boundaries are updated annually, so the vintage is the data year.')}

def ordinal(n):
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"

SLD_YEARS = [(0, 1999), (1, 2005), (2, 2009), (3, 2011), (4, 2013), (5, 2015), (6, 2017),
             (7, 2019), (8, 2021), (9, 2023), ('A', 2025), ('B', 2027)]

def sld(prefix):
    return {f'{prefix}{code}': v(f'Election in {y} or {y + 1}, session in {y + 1}-{y + 2} or {y + 2}-{y + 3}.')
            for code, y in SLD_YEARS}

CENSUS_VARIANTS = {
    '500': {f'{n:02d}': v(f'{ordinal(100 + n)} Congress (election in {1986 + 2 * n}, session in {1987 + 2 * n}-{1988 + 2 * n}).')
            for n in range(6, 22)},
    '610': sld('U'),
    '620': sld('L'),
    '310': {
        'M1': v('OMB Bulletin No. 10-02 delineations.', '2009-12-01'),
        'M2': v('OMB Bulletin No. 13-01 delineations.', '2013-02-28'),
        'M3': v('OMB Bulletin No. 15-01 delineations.', '2015-07-15'),
        'M4': v('OMB Bulletin No. 17-01 delineations.', '2017-08-15'),
        'M5': v('OMB Bulletin No. 18-04 delineations.', '2018-09-14'),
        'M6': v('OMB Bulletin No. 20-01 delineations. Used in 2020 Census data products.', '2020-03-06'),
        'M7': v('OMB Bulletin No. 23-01 delineations.', '2023-07-21'),
    },
    '400': {
        '00': v('2000 Census urban-rural classification, as used in 2000 Census data.'),
        'C0': v('2000 Census urban-rural classification. Used only in 2010 and 2011 ACS tabulations.'),
        'C1': v('2010 Census urban-rural classification. 2020 ACS tabulations use this code.'),
        'C2': v('2020 Census urban-rural classification. Used in 2020 Census tabulations.'),
        'C3': v('2030 Census urban-rural classification.'),
    },
    '860': {
        '00': v('2000 and 2010 Census ZCTA delineations. 2020 ACS tabulations use the 2010 delineation with this code.'),
        'Z2': v('2020 Census ZCTA delineation.'),
        'Z3': v('2030 Census ZCTA delineation.'),
    },
    '795': {
        '00': v('2000 and 2010 PUMA delineations.'),
        'P2': v('2020 PUMA delineation.'),
        'P3': v('2030 PUMA delineation.'),
    },
}

# Original model IDs, kept in their own field now that the GEOID codes are renumbered within each parent
LEGACY_ID_FIELDS = {'M20': 'TAZ2020', 'M21': 'MAZ2020', 'M22': 'GridMAZ20'}

# Current Census geographic components, from the 2020 Census DHC Technical Documentation, data dictionary p. 3-17
GEOCOMPS = {
    '00': {'description': 'Not a geographic component'},
    '01': {'description': 'Urban'},
    '43': {'description': 'Rural'},
    '44': {'description': 'Rural—place'},
    '48': {'description': 'Rural—not in place'},
    '89': {'description': 'American Indian Reservation and Trust Land—Federal'},
    '90': {'description': 'American Indian Reservation and Trust Land—State'},
    '91': {'description': 'Oklahoma Tribal Statistical Area'},
    '92': {'description': 'Tribal Designated Statistical Area'},
    '93': {'description': 'Alaska Native Village Statistical Area'},
    '94': {'description': 'State Designated Tribal Statistical Area'},
    '95': {'description': 'Hawaiian Home Land'},
    'A0': {'description': 'In metropolitan or micropolitan statistical area'},
    'A1': {'description': 'In metropolitan or micropolitan statistical area—in principal city'},
    'A2': {'description': 'In metropolitan or micropolitan statistical area—not in principal city'},
    'A3': {'description': 'In metropolitan or micropolitan statistical area—urban'},
    'A6': {'description': 'In metropolitan or micropolitan statistical area—rural'},
    'C0': {'description': 'In metropolitan statistical area'},
    'C1': {'description': 'In metropolitan statistical area—in principal city'},
    'C2': {'description': 'In metropolitan statistical area—not in principal city'},
    'C3': {'description': 'In metropolitan statistical area—urban'},
    'C6': {'description': 'In metropolitan statistical area—rural'},
    'E0': {'description': 'In micropolitan statistical area'},
    'E1': {'description': 'In micropolitan statistical area—in principal city'},
    'E2': {'description': 'In micropolitan statistical area—not in principal city'},
    'E3': {'description': 'In micropolitan statistical area—urban'},
    'E6': {'description': 'In micropolitan statistical area—rural'},
    'G0': {'description': 'Not in metropolitan or micropolitan statistical area'},
    'G1': {'description': 'Not in metropolitan or micropolitan statistical area—urban'},
    'G4': {'description': 'Not in metropolitan or micropolitan statistical area—rural'},
    'H0': {'description': 'Not in metropolitan statistical area'},
    'H1': {'description': 'Not in metropolitan statistical area—urban'},
    'H4': {'description': 'Not in metropolitan statistical area—rural'},
    'M1': {'description': 'In New England city and town area—in principal city'},
    'M2': {'description': 'In New England city and town area—not in principal city'},
    'M3': {'description': 'In New England city and town area—urban'},
    'M6': {'description': 'In New England city and town area—rural'},
}


def text(cell):
    value = re.sub(r'<br\s*/?>', ' ', cell.get('value') or '')
    value = html.unescape(re.sub(r'<[^>]+>', '', value))
    return re.sub(r'\s+', ' ', value).strip()


def clean(value):
    return None if value in ('', 'None') else value


def main():
    cells = list(ET.parse(DRAWIO).iter('mxCell'))
    kids = {}
    for c in cells:
        kids.setdefault(c.get('parent'), []).append(c)

    sumlevels = {}
    for table in kids['1']:
        if not (table.get('style') or '').startswith('shape=table;'):
            continue
        row = {text(k): clean(text(v)) for k, v in (kids[r.get('id')] for r in kids[table.get('id')])}
        sl = row['SL']
        assert sl not in sumlevels, f'duplicate sumlevel {sl}'
        variants = CENSUS_VARIANTS.get(sl, STANDARD)
        assert row['current_variant'] in variants, f'{sl}: current_variant not in its variant list'
        added = {
            'description': DESCRIPTIONS[sl],
            'legacyIdField': LEGACY_ID_FIELDS.get(sl),
            'variants': variants,
            'wof_placetype': row['W'],
        }
        sumlevels[sl] = {f: added[f] if f in added else row[f] for f in FIELD_ORDER}

    out = {'sumlevels': dict(sorted(sumlevels.items())), 'geocomps': GEOCOMPS}
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=4, ensure_ascii=False)
        f.write('\n')
    print(f"wrote {len(sumlevels)} sumlevels and {len(GEOCOMPS)} geocomps to {OUT.relative_to(ROOT)}")


if __name__ == '__main__':
    main()
