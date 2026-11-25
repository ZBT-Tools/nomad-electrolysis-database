from nomad_electrolysis.definitions import CHARACTERIZATION_FIELDS, SCHEMA_NAME
from nomad_electrolysis.schema_packages import electrolysis_schema


def test_schema_preserves_archive_identity_and_characterization_fields():
    schema = electrolysis_schema.load().all_definitions['ElectrolysisRecord']
    assert schema.qualified_name() == SCHEMA_NAME
    assert not schema.all_sub_sections
    for name in CHARACTERIZATION_FIELDS.values():
        assert name in schema.all_quantities
