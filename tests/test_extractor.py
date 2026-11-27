import json

import pytest

from nomad_electrolysis.definitions import CHARACTERIZATION_FIELDS, SCHEMA_NAME
from nomad_electrolysis.extractor import EVIDENCE, REVIEW_FILENAME, make_archives

CHANDA_ENTRY_COUNT = 4
NOMINAL_PURE_WATER_PH = 7


@pytest.mark.parametrize('explore', [False, True])
def test_flat_archive_keeps_the_pem_durability_operating_point(explore):
    evidence = json.loads(EVIDENCE.read_bytes())
    evidence['sources'][0].update(status='verified', license='CC-BY-4.0')
    evidence['characterization'] = {
        label: {'present': label == 'XPS'} for label in CHARACTERIZATION_FIELDS
    }
    measurements = {
        '#2': [
            {
                'quantity': 'test_duration',
                'method': 'PEM durability test',
                'method_id': 'pem_durability',
                'control_mode': 'constant_current',
                'current_density': 0.4,
                'unit': 'h',
                'value': 380,
                'source_locator': 'body/sec/p[1]',
            }
        ]
    }
    files = make_archives(evidence, measurements, explore=explore)

    assert len(files) == CHANDA_ENTRY_COUNT
    archive = files['chanda-70388-2.archive.json']
    data = archive['data']
    assert data['m_def'] == (SCHEMA_NAME if explore else 'ElectrolysisRecord')
    assert (data['durability_hours'], data['durability_current_density']) == (380, 0.4)
    assert data['review_file'] == REVIEW_FILENAME
    assert data['xps'] is True
    assert data['raman_in_situ'] is False
    assert data['ph'] == NOMINAL_PURE_WATER_PH
    assert data['ph_approximate']
    assert 'csv_only_fields' not in data
    assert 'electrolyte_concentration' not in data
    assert 'measurements' not in data
    assert archive['results']['eln']['methods'] == ['PEM durability test']
    assert 'Nb' in archive['results']['material']['elements']
    assert measurements['#2'][0]['source_locator'] == 'body/sec/p[1]'
