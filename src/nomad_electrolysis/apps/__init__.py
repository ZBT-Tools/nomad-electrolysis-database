"""Explore configuration for the electrolysis literature entries."""

from nomad.config.models.plugins import AppEntryPoint
from nomad.config.models.ui import (
    App,
    Axis,
    AxisLimitedScale,
    Column,
    Dashboard,
    Format,
    Layout,
    Markers,
    Menu,
    MenuItemHistogram,
    MenuItemPeriodicTable,
    MenuItemTerms,
    ResourceEnum,
    SearchQuantities,
    WidgetHistogram,
    WidgetPeriodicTable,
    WidgetScatterPlot,
    WidgetTerms,
)

from nomad_electrolysis.definitions import CHARACTERIZATION_FIELDS, SCHEMA_NAME


def field(name):
    return f'data.{name}#{SCHEMA_NAME}'


METHODS = 'results.eln.methods'
ELEMENTS = 'results.material.elements'
CATEGORIES = {
    'catalyst': 'Catalyst',
    'reaction': 'Reaction',
    'electrode_role': 'Electrode role',
    'electrolyte': 'Electrolyte',
    'technology': 'Electrolysis technology',
    'membrane': 'Membrane',
    'test_type': 'Test type',
    'setup_type': 'Cell configuration',
    'synthesis': 'Synthesis method',
}
NUMERIC_COLUMNS = [
    ('overpotential_at_10_ma_cm2', 'OER overpotential at 10 mA/cm²', 'mV', 1, True),
    ('cell_voltage_at_1_a_cm2', 'Cell voltage at 1 A/cm²', 'V', 3, True),
    ('durability_hours', 'Durability test duration', 'h', 1, True),
    (
        'durability_current_density',
        'Durability test current density',
        'A/cm^2',
        3,
        True,
    ),
    ('cell_temperature', 'Cell temperature', 'degC', 1, True),
    ('electrolyte_temperature', 'Electrolyte temperature', 'degC', 1, False),
    ('ph', 'pH', None, 2, False),
    ('catalyst_loading', 'Catalyst loading', 'mg/cm^2', 2, False),
    ('tafel_slope', 'Tafel slope (per decade)', 'mV', 1, False),
    (
        'charge_transfer_resistance',
        'Charge-transfer resistance (Rct)',
        'ohm*cm^2',
        2,
        False,
    ),
    ('mass_activity', 'Mass activity', 'A/g', 2, False),
    (
        'capacitance_normalized_activity',
        'Capacitance-normalized activity',
        'A/F',
        2,
        False,
    ),
    (
        'double_layer_capacitance_areal',
        'Areal double-layer capacitance',
        'uF/cm^2',
        1,
        False,
    ),
    ('degradation_rate', 'Degradation rate', 'uV/h', 1, False),
]
COLUMNS = [
    Column(search_quantity='entry_name', title='Entry', selected=True),
    Column(
        search_quantity=field('characterization_methods'),
        title='Characterization',
        selected=True,
    ),
    *(
        Column(
            search_quantity=field(name),
            title=title,
            selected=name in {'catalyst', 'test_type', 'electrode_role'},
        )
        for name, title in CATEGORIES.items()
    ),
    *(
        Column(
            search_quantity=field(name),
            title=title,
            unit=unit,
            format=Format(decimals=places),
            selected=selected,
        )
        for name, title, unit, places, selected in NUMERIC_COLUMNS
    ),
    *(
        Column(search_quantity=field(name), title=title)
        for title, name in CHARACTERIZATION_FIELDS.items()
    ),
    Column(search_quantity=METHODS, title='Measurement methods'),
    Column(search_quantity=field('article_doi'), title='Publication DOI'),
]

DASHBOARD = Dashboard(
    widgets=[
        WidgetPeriodicTable(
            title='Elements',
            search_quantity=ELEMENTS,
            layout={
                'sm': Layout(x=0, y=0, w=12, h=8),
                'md': Layout(x=0, y=0, w=18, h=8),
                'lg': Layout(x=0, y=0, w=12, h=8),
            },
        ),
        WidgetScatterPlot(
            title='Durability test duration vs. current density',
            description=(
                'Each point represents a reported test. The duration can reflect '
                'the planned test length. Tests at the same operating point and '
                'duration may overlap.'
            ),
            x=AxisLimitedScale(
                search_quantity=field('durability_current_density'),
                title='Durability test current density',
                unit='A/cm^2',
                scale='log',
            ),
            y=AxisLimitedScale(
                search_quantity=field('durability_hours'),
                title='Durability test duration',
                unit='h',
            ),
            markers=Markers(
                color=Axis(
                    search_quantity=field('setup_type'),
                    title='Cell configuration',
                )
            ),
            layout={
                'sm': Layout(x=0, y=8, w=12, h=7),
                'md': Layout(x=0, y=8, w=18, h=7),
                'lg': Layout(x=12, y=0, w=12, h=8),
            },
        ),
        WidgetTerms(
            title='Entries by cell configuration',
            description='Select a bar to filter the dashboard and results table.',
            search_quantity=field('setup_type'),
            show_input=False,
            layout={
                'sm': Layout(x=0, y=15, w=12, h=5),
                'md': Layout(x=0, y=15, w=8, h=6),
                'lg': Layout(x=0, y=8, w=10, h=6),
            },
        ),
        WidgetHistogram(
            title='Cell voltage at 1 A/cm²',
            description=(
                'Counts entries with a reported cell voltage at 1 A/cm². '
                'Select a cell configuration for a comparison within that configuration.'
            ),
            x=Axis(
                search_quantity=field('cell_voltage_at_1_a_cm2'),
                title='Cell voltage at 1 A/cm²',
                unit='V',
            ),
            y='linear',
            n_bins=12,
            autorange=True,
            show_input=False,
            layout={
                'sm': Layout(x=0, y=20, w=12, h=6),
                'md': Layout(x=8, y=15, w=10, h=6),
                'lg': Layout(x=10, y=8, w=14, h=6),
            },
        ),
    ]
)

electrolysis_app = AppEntryPoint(
    name='Electrolysis Gallery',
    description='Search curated electrolysis literature measurements.',
    app=App(
        label='Electrolysis',
        path='electrolysis',
        resource=ResourceEnum.ENTRIES,
        category='Use Cases',
        description='Compare published half-cell and single-cell electrolysis data.',
        readme=(
            'Each row represents a catalyst in a specific experimental setup. '
            'Compare overpotential and cell voltage at the indicated current densities. '
            'Characterization flags refer to the catalyst material studied in the publication. '
            'Values marked (CSV) came from the input table and are pending source verification. '
            'The upload review report includes additional operating points and source locations.'
        ),
        filters_locked={'section_defs.definition_qualified_name': [SCHEMA_NAME]},
        search_quantities=SearchQuantities(
            include=[
                ELEMENTS,
                METHODS,
                *(
                    column.search_quantity
                    for column in COLUMNS
                    if column.search_quantity != METHODS
                ),
            ],
        ),
        columns=COLUMNS,
        dashboard=DASHBOARD,
        menu=Menu(
            size='lg',
            items=[
                MenuItemTerms(search_quantity=METHODS, title='Measurement methods'),
                MenuItemPeriodicTable(search_quantity=ELEMENTS, title='Elements'),
                Menu(
                    title='Experimental setup',
                    items=[
                        MenuItemTerms(search_quantity=field(name), title=title)
                        for name, title in CATEGORIES.items()
                    ],
                ),
                Menu(
                    title='Measurements',
                    items=[
                        MenuItemHistogram(
                            x=Axis(search_quantity=field(name), unit=unit), title=title
                        )
                        for name, title, unit, _, _ in NUMERIC_COLUMNS
                    ],
                ),
                Menu(
                    title='Characterization',
                    items=[
                        MenuItemTerms(
                            search_quantity=field(name), title=title, show_input=False
                        )
                        for title, name in CHARACTERIZATION_FIELDS.items()
                    ],
                ),
            ],
        ),
    ),
)
