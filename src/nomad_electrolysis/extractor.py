"""Build a private NOMAD pilot upload from the gallery CSV and Chanda evidence."""

import argparse
import csv
import hashlib
import io
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from tempfile import NamedTemporaryFile
from zipfile import ZIP_DEFLATED, ZipFile

from nomad_electrolysis.chanda_fulltext import extract_fulltext
from nomad_electrolysis.definitions import (
    CHARACTERIZATION_FIELDS,
    COMPONENT_FIELDS,
    SCHEMA_NAME,
    archive_definitions,
)

EVIDENCE = Path(__file__).with_name('chanda_2026.json')
REVIEW_FILENAME = 'chanda-2026-review.json'
CSV_HEADER = ['Category Name', 'Types', 'Units']
CSV_METADATA_ROWS = 2
CSV_SOURCE = 'Chanda et al, 2026'
UNIT_ALIASES = {
    'M': 'mol/L',
    'mv dec-1': 'mV/dec',
    'Ohm cm2': 'ohm*cm^2',
    'A g-1': 'A/g',
    'A F-1': 'A/F',
    'mV h-1': 'mV/h',
    'mg/cm²': 'mg/cm^2',
    'V @ 1A / cm^2': 'V',
}
SETUP_UNITS = {'Electrolyte concentration': 'mol/L', 'Temperature (cell)': '°C'}
CSV_OPERATING_FIELDS = {
    'pH': ('ph', {'': 1}),
    'Temperature (cell)': ('cell_temperature', {'°C': 1}),
    'Temperature (electrolyte)': ('electrolyte_temperature', {'°C': 1}),
    'Catalyst loading': ('catalyst_loading', {'mg/cm^2': 1}),
    'Degradation': (
        'degradation_rate',
        {'mV/h': 1000, 'µV/h': 1, 'uV/h': 1, 'µV h^-1': 1},
    ),
}
GALLERY_FIELD_MAP = {
    'Catalyst': ('catalyst', None),
    'Reaction': ('reaction', None),
    'Electrolyte': ('electrolyte', None),
    'Technology': ('technology', None),
    'Membrane': ('membrane', None),
    'Test type': ('test_type', None),
    'Synthesis': ('synthesis', None),
    'pH': ('ph', None),
    'Temperature (cell)': ('cell_temperature', '°C'),
    'Temperature (electrolyte)': ('electrolyte_temperature', '°C'),
    'Catalyst loading': ('catalyst_loading', 'mg/cm²'),
    'Overpotential': ('overpotential_at_10_ma_cm2', 'mV'),
    'Tafel Slope': ('tafel_slope', 'mV/dec'),
    'Impedance': ('charge_transfer_resistance', 'Ω·cm²'),
    'Mass activity': ('mass_activity', 'A/g'),
    'Specific Activity': ('capacitance_normalized_activity', 'A/F'),
    'ECSA': ('double_layer_capacitance_areal', 'µF/cm²'),
    'Performance': ('cell_voltage_at_1_a_cm2', 'V at 1 A/cm²'),
    'Stability': ('durability_hours', 'h'),
    'Degradation': ('degradation_rate', 'µV/h'),
} | {label: (field, None) for label, field in CHARACTERIZATION_FIELDS.items()}


def read_gallery_csv(payload, columns):
    table = list(
        csv.reader(io.StringIO(payload.decode('utf-8-sig'), newline=''), strict=True)
    )
    if len(table) <= CSV_METADATA_ROWS or table[1][:3] != CSV_HEADER:
        raise ValueError(
            'Expected the gallery CSV with the publication row followed by the field header.'
        )
    header = table[1]
    column_names = header[3:]
    if len(column_names) != len(columns) or set(column_names) != set(columns):
        raise ValueError('CSV columns must match the curated Chanda evidence.')
    if table[0] != ['', '', ''] + [CSV_SOURCE] * len(columns):
        raise ValueError('Publication labels do not match the curated Chanda evidence.')

    fields = {}
    for row_number, row in enumerate(table[2:], 3):
        if not row or not any(row):
            continue
        if len(row) != len(header) or not row[0] or row[0] in fields:
            raise ValueError(f'Invalid or duplicate field at CSV row {row_number}.')
        field, declared_type, unit, *values = row
        fields[field] = {
            'row': row_number,
            'type': declared_type,
            'unit': unit,
            'values': dict(zip(column_names, values)),
        }
    for column, setup in columns.items():
        for field, expected in (
            ('Catalyst', setup['catalyst']),
            ('Test type', setup['csv_test_type']),
        ):
            actual = fields.get(field, {}).get('values', {}).get(column)
            if actual != expected:
                raise ValueError(
                    f'{column} {field} does not identify the expected Chanda sample: {expected}.'
                )
    return fields


def number(text):
    value = float(text.strip().replace(',', '.'))
    if not math.isfinite(value):
        raise ValueError('Non-finite numbers are not valid measurements.')
    return value


def compare_number(raw, csv_unit, value, unit):
    if UNIT_ALIASES.get(csv_unit, csv_unit) != unit:
        return 'conflict', 'The CSV unit does not match the mapped measurement unit.'
    try:
        matches = math.isclose(number(raw), value, rel_tol=1e-9, abs_tol=1e-12)
    except ValueError:
        return 'review', 'The CSV value cannot be interpreted as a finite number.'
    if matches:
        return 'matched', 'Value and mapped unit agree with the article.'
    return 'conflict', 'The CSV value differs from the article.'


# Keep separate early returns for each evidence and review status.
def compare_field(field, csv_cell, setup, column_info, metric):  # noqa: PLR0911
    raw, csv_unit = csv_cell
    if not raw.strip():
        return 'missing_in_csv', 'Empty CSV cell.', None
    if metric:
        value = metric['value']
        if field == 'ECSA':
            return (
                'conflict',
                'Article reports areal double-layer capacitance in mF/cm²; CSV labels it ECSA in µF/cm².',
                value,
            )
        status, note = compare_number(raw, csv_unit, value, metric['unit'])
        return status, note, value
    if field == 'pH':
        return (
            'review',
            'Check the pH and whether it was measured or estimated; preserve the original qualifier.',
            None,
        )
    if field == 'Electrolyte concentration' and 'feed_medium' in setup:
        return (
            'review',
            'DI-water feed is reported; verify the species and meaning of the CSV concentration.',
            None,
        )
    if field == 'Degradation':
        return (
            'review',
            'CSV rate and evaluation interval were not verified in the main article.',
            None,
        )
    if field == 'Synthesis':
        return (
            'review',
            'Electrodeposition is reported. Check thermal treatment and post-deposition steps for each sample.',
            'Electrodeposition',
        )
    if field == 'Test type':
        note = 'Three-electrode setup is reported; verify the vessel geometry.'
        if column_info['setup'] == 'pem_single_cell':
            return (
                'matched',
                'The article reports a PEM single cell.',
                column_info['setup'],
            )
        return 'review', note, column_info['setup']
    if field == 'Technology' and 'technology' not in setup:
        return (
            'review',
            'PEM is the application context for this half-cell measurement.',
            None,
        )

    source_text = {
        'Catalyst': column_info['catalyst'],
        'Reaction': 'OER',
        'Electrolyte': setup.get('electrolyte', setup.get('feed_medium')),
        'Membrane': setup.get('membrane'),
        'Technology': setup.get('technology'),
    }.get(field)
    if source_text is not None:
        agrees = raw.strip().casefold() == source_text.casefold()
        return (
            ('matched' if agrees else 'conflict'),
            'Compared with the source setup.',
            source_text,
        )

    source_quantity = {
        'Electrolyte concentration': setup.get('electrolyte_concentration'),
        'Temperature (cell)': setup.get('cell_temperature'),
    }.get(field)
    if source_quantity is not None:
        status, note = compare_number(
            raw, csv_unit, source_quantity, SETUP_UNITS[field]
        )
        return status, note, source_quantity
    return (
        'review',
        'No matching source value was verified for this CSV field and setup.',
        None,
    )


def measurement_records(evidence):
    by_column = defaultdict(list)
    by_field = {}
    for series in evidence['series']:
        method_id = series['method']
        method_details = {
            key: value
            for key, value in evidence['methods'][method_id].items()
            if key != 'label'
        }
        for column, original_value in series['values'].items():
            scale = series.get('source_scale', 1)
            record = {
                'quantity': series['quantity'],
                'value': round(original_value * scale, 12),
                'unit': series['unit'],
                'source_value': original_value,
                'source_unit': series.get('source_unit', series['unit']),
                'source_reference': series['reference'],
                'source_locator': series['source_locator'],
                'source_literal': series['source_literals'][column],
                'approximate': column in series.get('approximate', []),
                'method_id': method_id,
                'method': evidence['methods'][method_id]['label'],
                **method_details,
                **series.get('conditions', {}),
            }
            uncertainty = series.get('uncertainties', {}).get(column)
            if uncertainty is not None:
                record['uncertainty'] = round(uncertainty * scale, 12)
            for key in ('notes', 'condition_locator'):
                if key in series:
                    record[key] = series[key]
            by_column[column].append(record)
            by_field[column, series['field']] = record
    return by_column, by_field


def reconcile(fields, evidence, by_field, archives):
    entries = {
        archive['data']['csv_column']: archive['data'] for archive in archives.values()
    }
    checks = []
    for column, info in evidence['columns'].items():
        setup = evidence['setups'][info['setup']]
        entry = entries[column]
        for field, cell in fields.items():
            raw_value = cell['values'][column]
            metric = by_field.get((column, field))
            status, detail, source_value = compare_field(
                field, (raw_value, cell['unit']), setup, info, metric
            )
            source_unit = None
            reference = None
            locator = None
            if metric:
                source_unit = metric['unit']
                reference = metric['source_reference']
                source_value = metric['value']
                locator = metric['source_locator']
            elif source_value is not None:
                source_unit = SETUP_UNITS.get(field)
                reference = setup['setup_reference']
                if source_unit:
                    locator = setup.get('setup_numeric_locator')
            if field in CHARACTERIZATION_FIELDS:
                method = evidence['characterization'][field]
                status = method['status']
                detail = method['note']
                source_value = method['present']
                locator = method['source_locator']
                if raw_value and source_value is not None:
                    status = (
                        'matched'
                        if csv_boolean(raw_value) == source_value
                        else 'conflict'
                    )
            check = {
                'column': column,
                'row': cell['row'],
                'field': field,
                'csv_value': raw_value,
                'csv_unit': cell['unit'],
                'status': status,
                'detail': detail,
                'article_value': source_value,
                'article_unit': source_unit,
                'article_reference': reference,
                'article_locator': locator,
            }
            if field in GALLERY_FIELD_MAP:
                quantity, unit = GALLERY_FIELD_MAP[field]
                check['imported_quantity'] = quantity
                check['imported_value'] = entry.get(quantity)
                check['imported_unit'] = unit
                if quantity in entry['csv_only_fields']:
                    check['import_basis'] = 'csv_only'
            checks.append(check)
    return checks


def unique_measurement(measurements, **conditions):
    matches = [
        record
        for record in measurements
        if all(record.get(key) == value for key, value in conditions.items())
    ]
    return matches[0] if len(matches) == 1 else None


def benchmark_values(measurements, setup_type):
    values = {}
    if setup_type == 'oer_half_cell':
        point = unique_measurement(
            measurements, quantity='overpotential', unit='mV', current_density=0.01
        )
        if point:
            values['overpotential_at_10_ma_cm2'] = point['value']
        drift_quantity = 'electrode_potential_drift_rate'
    else:
        point = unique_measurement(
            measurements,
            quantity='cell_voltage',
            unit='V',
            current_density=1.0,
            voltage_correction='before_HFR_correction',
        )
        if point:
            values['cell_voltage_at_1_a_cm2'] = point['value']
        drift_quantity = 'cell_voltage_drift_rate'

    duration = unique_measurement(
        measurements,
        quantity='test_duration',
        unit='h',
        control_mode='constant_current',
    )
    if duration and 'current_density' in duration:
        values['durability_hours'] = duration['value']
        values['durability_current_density'] = duration['current_density']
        drift = unique_measurement(
            measurements,
            quantity=drift_quantity,
            unit='mV/h',
            method_id=duration['method_id'],
            current_density=duration['current_density'],
        )
        if drift:
            values['degradation_rate'] = round(drift['value'] * 1000, 12)
    return values


def csv_boolean(raw_value):
    values = {'true': True, 'false': False, '': False}
    normalized = raw_value.strip().casefold()
    if normalized not in values:
        raise ValueError(
            f'Invalid CSV presence flag {raw_value!r}. Expected true, false or a blank cell.'
        )
    return values[normalized]


def add_gallery_fields(data, fields, evidence, measurements):
    column = data['csv_column']
    csv_only = []
    for label, quantity in (
        ('Technology', 'technology'),
        ('Synthesis', 'synthesis'),
        ('Test type', 'test_type'),
    ):
        cell = fields.get(label)
        raw = cell['values'][column].strip() if cell else ''
        if raw and quantity not in data:
            data[quantity] = 'Single-cell' if raw.casefold() == 'single-cell' else raw
            if quantity != 'synthesis' and not (
                quantity == 'test_type' and data['setup_type'] == 'pem_single_cell'
            ):
                csv_only.append(quantity)
    if 'feed_medium' in data:
        data['electrolyte'] = data['feed_medium']

    for quantity in (
        'tafel_slope',
        'charge_transfer_resistance',
        'mass_activity',
        'capacitance_normalized_activity',
        'double_layer_capacitance_areal',
    ):
        match = unique_measurement(measurements, quantity=quantity)
        if match:
            factor = 1000 if quantity == 'double_layer_capacitance_areal' else 1
            data[quantity] = round(match['value'] * factor, 12)
    for label, (quantity, conversions) in CSV_OPERATING_FIELDS.items():
        if quantity in data or label not in fields:
            continue
        cell = fields[label]
        raw = cell['values'][column].strip()
        if not raw:
            continue
        unit = UNIT_ALIASES.get(cell['unit'], cell['unit'])
        if unit not in conversions:
            raise ValueError(f'Unsupported CSV unit {unit!r} for {label} ({column}).')
        approximate = raw.startswith(('~', '≈'))
        data[quantity] = round(number(raw.lstrip('~≈')) * conversions[unit], 12)
        csv_only.append(quantity)
        if quantity == 'ph':
            data['ph_approximate'] = approximate

    add_characterization_fields(data, fields, evidence['characterization'], csv_only)
    data['csv_only_fields'] = csv_only


def add_characterization_fields(data, fields, characterization, csv_only):
    present_methods = []
    for label, quantity in CHARACTERIZATION_FIELDS.items():
        presence = characterization[label]['present']
        if presence is None:
            cell = fields.get(label)
            raw = cell['values'][data['csv_column']] if cell else ''
            presence = csv_boolean(raw)
            if raw.strip():
                csv_only.append(quantity)
        data[quantity] = presence
        if presence:
            present_methods.append(f'{label} (CSV)' if quantity in csv_only else label)
    data['characterization_methods'] = ', '.join(present_methods)


def make_archives(evidence, by_column, fields, explore=False):
    article = next(
        source for source in evidence['sources'] if source['id'] == 'article'
    )
    if article['status'] != 'verified' or article['license'] != 'CC-BY-4.0':
        raise ValueError(
            'The article must have a verified CC BY 4.0 license in the reviewed evidence.'
        )
    files = {}
    schema = {} if explore else {'definitions': archive_definitions()}
    for column, info in evidence['columns'].items():
        setup = {
            field: value
            for field, value in evidence['setups'][info['setup']].items()
            if field not in {'setup_reference', 'setup_numeric_locator'}
        }
        setup_label = (
            'PEM single cell' if info['setup'] == 'pem_single_cell' else 'OER half cell'
        )
        record_id = f'chanda-70388-{column.removeprefix("#")}'
        measurements = by_column.get(column, [])
        data = {
            'm_def': SCHEMA_NAME if explore else 'ElectrolysisRecord',
            'name': f'{info["catalyst"]} | {setup_label} | {column}',
            'record_id': record_id,
            'csv_column': column,
            'catalyst': info['catalyst'],
            'reaction': 'OER',
            'setup_type': info['setup'],
            **setup,
            'article_doi': evidence['doi'],
            'article_citation': evidence['citation'],
            'article_url': article['url'],
            'article_license': article['license'],
            'review_file': REVIEW_FILENAME,
            'release_status': 'test_only',
            **benchmark_values(measurements, info['setup']),
        }
        add_gallery_fields(data, fields, evidence, measurements)
        elements = set()
        for field in COMPONENT_FIELDS:
            if field in data:
                composition = evidence['component_compositions'][data[field]][
                    'elements'
                ]
                data[f'{field}_elements'] = composition
                elements.update(composition)
        files[f'{record_id}.archive.json'] = {
            **schema,
            'metadata': {'entry_name': data['name']},
            'data': data,
            'results': {
                'material': {'elements': sorted(elements)},
                'eln': {
                    'methods': sorted({record['method'] for record in measurements})
                },
            },
        }
    return files


def json_text(value):
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n'


def build_package(csv_path, output_dir, article_path, explore=False):
    evidence_bytes = EVIDENCE.read_bytes()
    evidence = json.loads(evidence_bytes)
    payload = csv_path.read_bytes()
    fields = read_gallery_csv(payload, evidence['columns'])
    evidence = extract_fulltext(article_path.read_bytes(), evidence)
    by_column, by_field = measurement_records(evidence)
    files = make_archives(evidence, by_column, fields, explore)
    checks = reconcile(fields, evidence, by_field, files)
    report = {
        'format_version': 6,
        'release_status': 'test_only',
        'doi': evidence['doi'],
        'citation': evidence['citation'],
        'extraction_method': evidence['extraction_method'],
        'input': {'name': csv_path.name, 'sha256': hashlib.sha256(payload).hexdigest()},
        'evidence_sha256': hashlib.sha256(evidence_bytes).hexdigest(),
        'sources': evidence['sources'],
        'setups': evidence['setups'],
        'component_compositions': evidence['component_compositions'],
        'characterization_scope': 'Catalyst material in the checked main article; flags do not imply characterization of the assembled PEM cell.',
        'characterization': evidence['characterization'],
        'unit_notes': [
            {
                'field': 'ECSA',
                'table_unit': 'µF/cm²',
                'paper_unit': 'mF/cm²',
                'note': 'The paper reports areal double-layer capacitance. Values are converted to µF/cm². No ECSA was derived.',
            },
            {
                'field': 'Degradation',
                'table_unit': 'µV/h',
                'paper_unit': 'mV/h',
                'note': 'Both the article and the CSV use mV/h. Gallery values are multiplied by 1000 for µV/h.',
            },
        ],
        'summary': dict(Counter(check['status'] for check in checks)),
        'entry_count': len(files),
        'trial_count': sum(
            len({record['method_id'] for record in records})
            for records in by_column.values()
        ),
        'measurement_count': sum(map(len, by_column.values())),
        'measurements': dict(by_column),
        'notes': [
            'Archives contain flat comparison fields. Measurement and license evidence and original CSV values are in this report.',
            'Each sample column has one archive. Trial count refers to the distinct methods within each column.',
            'A matching CSV value does not imply that every measurement condition was reported.',
            'The NOMAD element index contains the union of the documented components in each trial.',
            'The ZIP is intended for an unpublished Test-Oasis upload.',
        ],
        'checks': checks,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    package_name = (
        'chanda-2026-explore.zip' if explore else 'chanda-2026-test-oasis.zip'
    )
    package_path = output_dir / package_name
    report_path = output_dir / REVIEW_FILENAME
    # Stage the ZIP in the destination directory before replacing the previous build.
    with NamedTemporaryFile(dir=output_dir, delete=False) as tmp:
        temporary_path = Path(tmp.name)
    try:
        with ZipFile(temporary_path, 'w', compression=ZIP_DEFLATED) as package:
            for name, contents in files.items():
                package.writestr(name, json_text(contents))
            package.writestr(report_path.name, json_text(report))
        temporary_path.replace(package_path)
    finally:
        temporary_path.unlink(missing_ok=True)
    report_path.write_bytes(json_text(report).encode('utf-8'))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        'csv', type=Path, help='Gallery CSV in UTF-8 (including optional BOM).'
    )
    parser.add_argument(
        '--article-xml',
        type=Path,
        required=True,
        help='Full text of Chanda et al. in JATS XML.',
    )
    parser.add_argument('--output-dir', type=Path, default=Path('output'))
    parser.add_argument(
        '--explore',
        action='store_true',
        help='Build archives for the installed Electrolysis Explore plugin.',
    )
    args = parser.parse_args()
    try:
        report = build_package(
            args.csv, args.output_dir, args.article_xml, explore=args.explore
        )
    except (OSError, ValueError, csv.Error) as error:
        parser.exit(1, f'Import preparation failed: {error}\n')
    print(
        f'Created {report["entry_count"]} entries with {report["measurement_count"]} measurements.'
    )
    print(json.dumps(report['summary'], sort_keys=True))
    print(args.output_dir.resolve())


if __name__ == '__main__':
    main()
