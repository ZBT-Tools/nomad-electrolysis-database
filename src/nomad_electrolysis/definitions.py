"""Metainfo definitions shared by standalone and plugin-backed archives."""

SCHEMA_NAME = 'nomad_electrolysis.schema.ElectrolysisRecord'
COMPONENT_FIELDS = (
    'catalyst',
    'electrolyte',
    'feed_medium',
    'substrate',
    'membrane',
    'cathode_catalyst',
)

BENCHMARK_UNITS = {
    'overpotential_at_10_ma_cm2': 'mV',
    'cell_voltage_at_1_a_cm2': 'V',
    'durability_hours': 'h',
    'durability_current_density': 'A/cm**2',
}

CHARACTERIZATION_FIELDS = {
    'XPS': 'xps',
    'XRD': 'xrd',
    'SEM': 'sem',
    'TEM': 'tem',
    'Raman in-situ': 'raman_in_situ',
    'Raman ex-situ': 'raman_ex_situ',
    'XAS in-situ': 'xas_in_situ',
    'XAS ex-situ': 'xas_ex_situ',
    'ICP-MS': 'icp_ms',
}

GALLERY_UNITS = {
    'electrolyte_temperature': 'degC',
    'catalyst_loading': 'mg/cm**2',
    'tafel_slope': 'mV',
    'charge_transfer_resistance': 'ohm*cm**2',
    'mass_activity': 'A/g',
    'capacitance_normalized_activity': 'A/F',
    'double_layer_capacitance_areal': 'uF/cm**2',
    'degradation_rate': 'uV/h',
}


def quantity_definitions(strings, numbers, units):
    return (
        {name: {'type': 'str'} for name in strings.split()}
        | {name: {'type': 'np.float64'} for name in numbers.split()}
        | {name: {'type': 'np.float64', 'unit': unit} for name, unit in units.items()}
    )


def archive_definitions():
    records = quantity_definitions(
        'name record_id csv_column catalyst reaction electrode_role setup_type '
        'technology electrolyte substrate feed_medium membrane cathode_catalyst test_type synthesis '
        'characterization_methods '
        'article_doi article_license article_citation article_url review_file release_status',
        'ph',
        {
            'electrolyte_concentration': 'mol/L',
            'cell_temperature': 'degC',
            'active_area': 'cm**2',
        }
        | BENCHMARK_UNITS
        | GALLERY_UNITS,
    )
    records['ph_approximate'] = {'type': 'bool'}
    records['csv_only_fields'] = {'type': 'str', 'shape': ['*']}
    records['review_file']['description'] = (
        'File in the same upload with measurement and license provenance.'
    )
    records['tafel_slope']['description'] = (
        'Potential change in mV per decade of log10 current.'
    )
    records['double_layer_capacitance_areal']['description'] = (
        'Areal double-layer capacitance. The import table labels this quantity ECSA.'
    )
    for label, field in CHARACTERIZATION_FIELDS.items():
        records[field] = {
            'type': 'bool',
            'description': f'{label} reported for the catalyst in the source. Presence flag.',
        }
    for field in COMPONENT_FIELDS:
        records[f'{field}_elements'] = {
            'type': 'str',
            'shape': ['*'],
            'description': f'Element symbols for the reported {field.replace("_", " ")}.',
        }
    return {
        'name': 'Electrolysis pilot',
        'sections': {
            'ElectrolysisRecord': {
                'base_sections': ['nomad.datamodel.data.EntryData'],
                'quantities': records,
            },
        },
    }
