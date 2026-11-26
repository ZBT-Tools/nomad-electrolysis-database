import pytest

from nomad_electrolysis.literature import apply_sample, read_table


def test_literature_preserves_existing_cells_and_refuses_ambiguous_evidence():
    gallery = b',,,Earlier study\nCategory Name,Types,Units,#1\nCatalyst,,,Ni\n'
    table = read_table(gallery, add_rows=True)
    evidence_page = 2
    source = {'citation': 'New study', 'doi': '10.1234/test'}
    sample = {
        'column': '#2',
        'label': 'Duration test',
        'fields': {
            'Durability current density': {
                'pattern': r'At (?P<value>\d+) mA/cm2',
                'page': evidence_page,
                'location': 'Duration test',
                'reported_unit': 'mA/cm²',
                'unit': 'A/cm²',
                'factor': '0.001',
            },
        },
    }
    checks = []
    apply_sample(table, sample, source, ['Abstract', 'At 100 mA/cm2.'], checks)
    assert table[2] == ['Catalyst', '', '', 'Ni', '']
    assert table[-1][-1] == '0.100'
    assert checks[0]['page'] == evidence_page
    assert checks[0]['reported_number'] == '100'

    with pytest.raises(ValueError, match='expected one match, got 2'):
        apply_sample(
            table, sample, source, ['Abstract', 'At 100 mA/cm2. At 200 mA/cm2.'], []
        )
    assert table[-1][-1] == '0.100'
