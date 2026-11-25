from nomad_electrolysis.apps import electrolysis_app, field
from nomad_electrolysis.definitions import SCHEMA_NAME


def test_app_keeps_adjacent_durability_columns():
    app = electrolysis_app.app
    assert app.filters_locked['section_defs.definition_qualified_name'] == [SCHEMA_NAME]
    selected = [column.search_quantity for column in app.columns if column.selected]
    position = selected.index(field('durability_hours'))
    assert selected[position + 1] == field('durability_current_density')
