"""Package a reviewed gallery CSV for an unpublished NOMAD upload."""

import argparse
import csv
import json
import re
from collections import defaultdict
from copy import deepcopy
from pathlib import Path

from nomad_electrolysis.chanda_fulltext import extract_fulltext
from nomad_electrolysis.definitions import (
    CHARACTERIZATION_FIELDS,
    COMPONENT_FIELDS,
    SCHEMA_NAME,
    archive_definitions,
)
from nomad_electrolysis.extractor import (
    CSV_SOURCE,
    EVIDENCE,
    UNIT_ALIASES,
    csv_boolean,
    make_archives,
    measurement_records,
    number,
    read_gallery_csv,
    reconcile,
    write_archive_zip,
)
from nomad_electrolysis.literature import APPROVED_ROWS, digest, read_table

REVIEW_NAME = 'gallery-import-review.json'
TEXT_FIELDS = {
    'Catalyst': 'catalyst',
    'Reaction': 'reaction',
    'Electrode role': 'electrode_role',
    'Electrolyte': 'electrolyte',
    'Technology': 'technology',
    'Membrane': 'membrane',
    'Test type': 'test_type',
    'Synthesis': 'synthesis',
}
NUMERIC_FIELDS = {
    'Electrolyte concentration': ('electrolyte_concentration', 'mol/L', 1),
    'pH': ('ph', '', 1),
    'Temperature (cell)': ('cell_temperature', '°C', 1),
    'Temperature (electrolyte)': ('electrolyte_temperature', '°C', 1),
    'Catalyst loading': ('catalyst_loading', 'mg/cm^2', 1),
    'Overpotential': ('overpotential_at_10_ma_cm2', 'mV', 1),
    'Tafel Slope': ('tafel_slope', 'mV/dec', 1),
    'Impedance': ('charge_transfer_resistance', 'ohm*cm^2', 1),
    'Mass activity': ('mass_activity', 'A/g', 1),
    'Specific Activity': ('capacitance_normalized_activity', 'A/F', 1),
    'ECSA': ('double_layer_capacitance_areal', 'µF cm-2', 1),
    'Performance': ('cell_voltage_at_1_a_cm2', 'V @ 1A / cm^2', 1),
    'Stability': ('durability_hours', 'h', 1),
    'Degradation': ('degradation_rate', 'mV/h', 1000),
    'Durability current density': ('durability_current_density', 'A/cm²', 1),
}
METHOD_FIELDS = {
    'Performance': 'Polarization curve',
    'Impedance': 'Electrochemical impedance spectroscopy',
    'Durability current density': 'Galvanostatic durability test',
}


def reviewed_columns(table, review):
    sources = {source['doi']: source for source in review['sources']}
    columns = {
        column: (index, table[0][index]) for index, column in enumerate(table[1][3:], 3)
    }
    cells = defaultdict(dict)
    for cell in review['cells']:
        column, field = cell['column'], cell['field']
        index, citation = columns[column]
        label, _, unit, *values = table[cell['row'] - 1]
        if (
            (field, cell['unit'], cell['value']) != (label, unit, values[index - 3])
            or sources[cell['doi']]['citation'] != citation
            or field in cells[column]
        ):
            raise ValueError(f'{column} {field}: review and CSV disagree')
        cells[column][field] = cell
    return sources, cells


def numeric_value(field, value, unit):
    quantity, expected, factor = NUMERIC_FIELDS[field]
    if unit != expected:
        if field == 'Performance' or UNIT_ALIASES.get(unit) != expected:
            raise ValueError(f'{field}: unexpected CSV unit {unit!r}')
    approximate = field == 'pH' and value.startswith(('~', '≈'))
    mapped = {quantity: number(value.lstrip('~≈') if approximate else value) * factor}
    if field == 'pH':
        mapped['ph_approximate'] = approximate
    return mapped


def gallery_quantities(cells):
    data = {}
    for field, cell in cells.items():
        value, unit = cell['value'], cell['unit']
        if field in TEXT_FIELDS:
            data[TEXT_FIELDS[field]] = (
                'Single-cell'
                if field == 'Test type' and value.casefold() == 'single-cell'
                else value
            )
        elif field in NUMERIC_FIELDS:
            data.update(numeric_value(field, value, unit))
        elif field in CHARACTERIZATION_FIELDS:
            data[CHARACTERIZATION_FIELDS[field]] = csv_boolean(value)
        else:
            raise ValueError(f'No archive mapping for CSV field {field!r}')
    data['characterization_methods'] = ', '.join(
        label for label, field in CHARACTERIZATION_FIELDS.items() if data.get(field)
    )
    return data


def reviewed_archive(column, cells, sources, components):
    first = next(iter(cells.values()))
    doi, sample = first['doi'], first['sample']
    if any((cell['doi'], cell['sample']) != (doi, sample) for cell in cells.values()):
        raise ValueError(f'{column}: conflicting sample identities in review')
    source = sources[doi]
    record_id = f'electrolysis-{digest(doi.encode())[:12]}-{column[1:]}'
    name = f'{sample} | {source["citation"]} | {column}'
    data = {
        'm_def': SCHEMA_NAME,
        'name': name,
        'record_id': record_id,
        'csv_column': column,
        'article_doi': doi,
        'article_citation': source['citation'],
        'article_url': source['url'],
        'article_license': source['license']['status'],
        'review_file': REVIEW_NAME,
        'release_status': 'test_only',
        **gallery_quantities(cells),
    }
    if data.get('test_type') == 'Single-cell' and data.get('technology'):
        data['setup_type'] = f'{data["technology"].lower()}_single_cell'
    elements = set()
    for field in COMPONENT_FIELDS:
        name_in_csv = data.get(field)
        if name_in_csv in components:
            symbols = components[name_in_csv]
            data[f'{field}_elements'] = symbols
            elements.update(symbols)
    methods = {method for field, method in METHOD_FIELDS.items() if field in cells}
    return {
        'metadata': {'entry_name': name},
        'data': data,
        'results': {
            'material': {'elements': sorted(elements)},
            'eln': {'methods': sorted(methods)},
        },
    }


def legacy_archives(payload, article_xml):
    if article_xml is None:
        raise ValueError('The curated CSV columns require the original JATS XML')
    profile = json.loads(EVIDENCE.read_bytes())
    fields = read_gallery_csv(payload, profile['columns'], allow_extra_columns=True)
    fields = {
        name: field for name, field in fields.items() if name not in APPROVED_ROWS
    }
    evidence = extract_fulltext(article_xml.read_bytes(), profile)
    measurements, by_field = measurement_records(evidence)
    archives = make_archives(evidence, measurements, fields, explore=True)
    review = {
        'sources': evidence['sources'],
        'measurements': dict(measurements),
        'checks': reconcile(fields, evidence, by_field, archives),
    }
    return archives, review


def create_archives(payload, table, review, article_xml, components):
    sources, cells = reviewed_columns(table, review)
    archives = {}
    if CSV_SOURCE in table[0][3:]:
        archives, review['legacy_review'] = legacy_archives(payload, article_xml)
    legacy_by_column = {a['data']['csv_column']: a['data'] for a in archives.values()}
    for index, column in enumerate(table[1][3:], 3):
        if not re.fullmatch(r'#[1-9][0-9]*', column):
            raise ValueError(f'Invalid CSV column {column!r}')
        reviewed = cells[column]
        if column in legacy_by_column:
            data = legacy_by_column[column]
            mapped = gallery_quantities(reviewed)
            if (
                mapped['durability_current_density']
                != data['durability_current_density']
            ):
                raise ValueError(
                    f'{column}: durability current differs from legacy evidence'
                )
            data.update(
                electrode_role=mapped['electrode_role'], review_file=REVIEW_NAME
            )
            continue
        populated = {row[0] for row in table[2:] if row[index]}
        if not populated or populated != reviewed.keys():
            raise ValueError(
                f'{column}: all populated cells must have matching evidence'
            )
        archive = reviewed_archive(column, reviewed, sources, components)
        archives[f'{archive["data"]["record_id"]}.archive.json'] = archive
    return archives


def build_gallery_packages(
    csv_path, review_path, output_dir, *, article_xml=None, components=None
):
    payload = csv_path.read_bytes()
    review = json.loads(review_path.read_bytes())
    if digest(payload) != review['output_sha256']:
        raise ValueError('CSV checksum differs from the reviewed CSV')
    table = read_table(payload, add_rows=False)
    archives = create_archives(payload, table, review, article_xml, components or {})
    review['release_status'] = 'test_only'
    review['entry_count'] = len(archives)
    review['component_elements'] = components or {}
    review['archive_notes'] = [
        'Unpublished test upload. The release status is informational.',
        'Archive degradation values are in µV/h. CSV values and source evidence are retained here.',
        'New records index documented elements in mapped components and methods supported by populated fields.',
    ]
    files = {REVIEW_NAME: review}
    write_archive_zip(output_dir / 'gallery-explore-test-only.zip', archives | files)
    standalone = deepcopy(archives)
    for archive in standalone.values():
        archive['data']['m_def'] = 'ElectrolysisRecord'
        archive['definitions'] = archive_definitions()
    write_archive_zip(
        output_dir / 'gallery-standalone-test-only.zip', standalone | files
    )
    return len(archives)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv', type=Path)
    parser.add_argument('review', type=Path)
    parser.add_argument('--article-xml', type=Path)
    parser.add_argument(
        '--components',
        type=Path,
        help='Reviewed material labels and their element symbols (JSON).',
    )
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    try:
        components = (
            json.loads(args.components.read_bytes()) if args.components else None
        )
        count = build_gallery_packages(
            args.csv,
            args.review,
            args.output_dir,
            article_xml=args.article_xml,
            components=components,
        )
    except (OSError, ValueError, KeyError, csv.Error) as error:
        parser.exit(1, f'Gallery packaging failed: {error}\n')
    print(
        f'Wrote two packages with {count} entries each to {args.output_dir.resolve()}'
    )


if __name__ == '__main__':
    main()
