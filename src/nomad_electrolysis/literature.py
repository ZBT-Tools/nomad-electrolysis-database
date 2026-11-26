"""Extend a gallery CSV from reviewed, source-anchored literature profiles."""

import argparse
import csv
import hashlib
import io
import json
import re
from decimal import Decimal, InvalidOperation
from html import escape
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree import ElementTree

from nomad_electrolysis.extractor import CSV_HEADER, CSV_METADATA_ROWS

APPROVED_ROWS = {
    'Electrode role': ('Anode, Cathode', ''),
    'Durability current density': ('[numerical]', 'A/cm²'),
}


def normalized(text):
    return ' '.join(text.replace('\x00', '−').split())


def digest(payload):
    return hashlib.sha256(payload).hexdigest()


def read_source(path, payload):
    if path.suffix.lower() == '.pdf':
        try:
            from pypdf import PdfReader
        except ImportError as error:
            raise ValueError('Install the literature extra to read PDFs.') from error
        return [
            normalized(page.extract_text())
            for page in PdfReader(io.BytesIO(payload)).pages
        ]
    if path.suffix.lower() == '.xml':
        root = ElementTree.fromstring(payload)
        return [
            normalized(''.join(node.itertext()))
            for node in root.iter()
            if node.tag in {'p', 'article-id', 'license-p'}
        ]
    return [normalized(page) for page in payload.decode('utf-8-sig').split('\f')]


def require_match(rule, pages):
    page = rule.get('page')
    if page is not None and not 1 <= page <= len(pages):
        raise ValueError(f'Invalid source page {page}')
    candidates = pages if page is None else pages[page - 1 : page]
    matches = [
        match for source in candidates for match in re.finditer(rule['pattern'], source)
    ]
    if len(matches) != 1:
        raise ValueError(f'{rule["location"]}: expected one match, got {len(matches)}')
    return matches[0]


def extract_cell(rule, pages, unit):
    if rule['unit'] != unit:
        raise ValueError(
            f'Profile unit {rule["unit"]!r} differs from CSV unit {unit!r}'
        )
    match = require_match(rule, pages)
    original = match.groupdict().get('value')
    if original is None:
        value = rule['value']
        if not value.strip() or value.lstrip().startswith(('=', '+', '-', '@')):
            raise ValueError('Missing or invalid categorical CSV value')
    else:
        factor = Decimal(rule.get('factor', '1'))
        converted = Decimal(original.replace(',', '.')) * factor
        if not converted.is_finite():
            raise ValueError('Non-finite numeric CSV value')
        value = format(converted, 'f')
    return {
        'value': value,
        'unit': unit,
        'reported_number': original,
        'reported_unit': rule.get('reported_unit'),
        'factor': rule.get('factor'),
        'page': rule.get('page'),
        'location': rule['location'],
        'reference_url': rule.get('reference_url'),
        'note': rule.get('note'),
    }


def read_table(payload, add_rows):
    table = list(csv.reader(io.StringIO(payload.decode('utf-8-sig')), strict=True))
    if len(table) <= CSV_METADATA_ROWS or table[1][:3] != CSV_HEADER:
        raise ValueError('Expected the publication row and gallery field header')
    width = len(table[1])
    if any(len(row) != width for row in table):
        raise ValueError('Gallery CSV has inconsistent row lengths')
    columns = table[1][3:]
    labels = [row[0] for row in table[2:]]
    if len(set(columns)) != len(columns) or len(set(labels)) != len(labels):
        raise ValueError('Duplicate CSV column or field')
    if add_rows:
        for label, (kind, unit) in APPROVED_ROWS.items():
            if label not in labels:
                table.append([label, kind, unit, *([''] * len(columns))])
    return table


def apply_sample(table, sample, source, pages, checks):
    column = sample['column']
    header = table[1]
    labels = {row[0]: i for i, row in enumerate(table[2:], 2)}
    unknown = sample['fields'].keys() - labels.keys()
    if unknown:
        raise ValueError(f'{column}: fields absent from CSV: {sorted(unknown)}')
    if column in header[3:]:
        index = header.index(column)
        if table[0][index] != source['citation']:
            raise ValueError(f'{column}: existing column has a different citation')
    else:
        index = len(header)
        for row in table:
            row.append('')
        table[0][index], table[1][index] = source['citation'], column

    for field, rule in sample['fields'].items():
        row_number = labels[field]
        row = table[row_number]
        try:
            cell = extract_cell(rule, pages, row[2])
        except (ValueError, InvalidOperation) as error:
            raise ValueError(f'{column} {field}: {error}') from error
        if row[index] and row[index] != cell['value']:
            raise ValueError(f'{column} {field}: would overwrite {row[index]!r}')
        row[index] = cell['value']
        checks.append(
            {
                'column': column,
                'row': row_number + 1,
                'sample': sample['label'],
                'field': field,
                'doi': source['doi'],
                **cell,
            }
        )


def link(url, label):
    if urlsplit(url).scheme not in {'https', 'file'}:
        raise ValueError(f'Unsupported link: {url}')
    return f'<a href="{escape(url)}">{escape(label)}</a>'


def review_html(report, pdf_links):
    sections = []
    for source in report['sources']:
        doi = source['doi']
        license_info = source['license']
        publisher = link(source['url'], 'Publication')
        proof = link(license_info['url'], 'License evidence')
        if doi in pdf_links and (license_page := license_info.get('page')):
            proof += ' · ' + link(
                f'{pdf_links[doi]}#page={license_page}', 'License notice in PDF'
            )
        head = (
            f'<h2>{escape(source["citation"])}</h2>'
            f'<p>{publisher} · {proof} · {escape(license_info["status"])}'
            f' · {escape(license_info["location"])}</p>'
        )
        notes = ''.join(f'<li>{escape(note)}</li>' for note in source.get('notes', []))
        rows = []
        for cell in report['cells']:
            if cell['doi'] != doi:
                continue
            reference_url = cell['reference_url']
            location = (
                link(reference_url, cell['location'])
                if reference_url
                else escape(cell['location'])
            )
            page = cell['page']
            if page and doi in pdf_links:
                location += ' · ' + link(
                    f'{pdf_links[doi]}#page={page}', f'PDF page {page}'
                )
            raw = cell['reported_number'] or ''
            if raw:
                raw += ' ' + (cell['reported_unit'] or cell['unit'])
            rows.append(
                '<tr><td>'
                + escape(f'{cell["column"]} · Row {cell["row"]}')
                + '</td><td>'
                + escape(cell['sample'])
                + '</td><td>'
                + escape(cell['field'])
                + '</td><td>'
                + escape(f'{cell["value"]} {cell["unit"]}'.strip())
                + '</td><td>'
                + escape(raw)
                + '</td><td>'
                + location
                + '</td><td>'
                + escape(cell['note'] or '')
                + '</td></tr>'
            )
        sections.append(
            head
            + (f'<ul>{notes}</ul>' if notes else '')
            + '<table><thead><tr><th>CSV</th><th>Sample</th><th>Field</th><th>Value</th>'
            '<th>Reported value</th><th>Source location</th><th>Notes</th>'
            '</tr></thead><tbody>' + ''.join(rows) + '</tbody></table>'
        )
    return (
        '<!doctype html><html lang="en"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>Electrolysis Gallery Review Report</title>'
        '<style>body{font:16px system-ui;margin:2rem;color:#162333}'
        'table{border-collapse:collapse;width:100%}'
        'td,th{padding:.55rem;border:1px solid #cad3dd;text-align:left;vertical-align:top}'
        'th{background:#e9eff5}tr:nth-child(even){background:#f6f8fa}</style>'
        '<h1>Electrolysis Gallery Review Report</h1>'
        '<p>For internal review. The tables list the CSV cells supported by the sources checked in this run.</p>'
        + ''.join(sections)
        + '</html>\n'
    )


def extend_gallery(csv_path, inputs, output_dir, *, add_rows=False):
    """Apply (profile path, source path) pairs and write the CSV and review reports."""
    payload = csv_path.read_bytes()
    table = read_table(payload, add_rows)
    report = {
        'release_status': 'internal_review',
        'input_sha256': digest(payload),
        'sources': [],
        'cells': [],
    }
    pdf_links = {}
    seen_dois, seen_columns = set(), set()
    for profile_path, source_path in inputs:
        if not source_path.is_file():
            raise ValueError(f'Source file missing: {source_path}')
        profile_bytes = profile_path.read_bytes()
        profile = json.loads(profile_bytes)
        source = profile['source']
        doi = source['doi']
        if doi in seen_dois:
            raise ValueError(f'Duplicate source DOI: {doi}')
        seen_dois.add(doi)
        source_bytes = source_path.read_bytes()
        pages = read_source(source_path, source_bytes)
        if not any(doi.lower() in page.lower() for page in pages):
            raise ValueError(f'Source document does not contain DOI {doi}')
        license_info = source['license']
        if 'pattern' in license_info:
            require_match(license_info, pages)
        if source_path.suffix.lower() == '.pdf':
            pdf_links[doi] = source_path.resolve().as_uri()
        report['sources'].append(
            {
                **source,
                'license': {
                    key: value
                    for key, value in license_info.items()
                    if key != 'pattern'
                },
                'source_sha256': digest(source_bytes),
                'profile_sha256': digest(profile_bytes),
                'source_file': source_path.name,
            }
        )
        for sample in profile['samples']:
            column = sample['column']
            if not re.fullmatch(r'#[1-9][0-9]*', column) or column in seen_columns:
                raise ValueError(f'Invalid or duplicate column: {column}')
            seen_columns.add(column)
            apply_sample(table, sample, source, pages, report['cells'])

    csv_output = output_dir / 'gallery-extended.csv'
    if csv_path.resolve() == csv_output.resolve():
        raise ValueError('Choose an output directory separate from the input CSV')
    buffer = io.StringIO(newline='')
    csv.writer(buffer).writerows(table)
    csv_bytes = buffer.getvalue().encode('utf-8-sig')
    report['output_sha256'] = digest(csv_bytes)
    html = review_html(report, pdf_links)
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_output.write_bytes(csv_bytes)
    (output_dir / 'gallery-review.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8'
    )
    (output_dir / 'gallery-review.html').write_text(html, encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv', type=Path)
    parser.add_argument(
        '--source',
        nargs=2,
        metavar=('PROFILE', 'DOCUMENT'),
        type=Path,
        action='append',
        required=True,
    )
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--add-electrode-and-durability-rows', action='store_true')
    args = parser.parse_args()
    try:
        report = extend_gallery(
            args.csv,
            args.source,
            args.output_dir,
            add_rows=args.add_electrode_and_durability_rows,
        )
    except (OSError, ValueError, KeyError, csv.Error, ElementTree.ParseError) as error:
        parser.exit(1, f'CSV preparation failed: {error}\n')
    print(f'Wrote {len(report["cells"])} reviewed cells to {args.output_dir.resolve()}')


if __name__ == '__main__':
    main()
