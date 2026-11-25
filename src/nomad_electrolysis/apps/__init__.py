"""Explore configuration for the electrolysis literature entries."""

from nomad.config.models.plugins import AppEntryPoint
from nomad.config.models.ui import (
    App,
    Axis,
    Column,
    Format,
    Menu,
    MenuItemHistogram,
    MenuItemPeriodicTable,
    MenuItemTerms,
    ResourceEnum,
    SearchQuantities,
)

from nomad_electrolysis.definitions import CHARACTERIZATION_FIELDS, SCHEMA_NAME


def field(name):
    return f'data.{name}#{SCHEMA_NAME}'


METHODS = 'results.eln.methods'
ELEMENTS = 'results.material.elements'
CATEGORIES = {
    'catalyst': 'Katalysator',
    'reaction': 'Reaktion',
    'electrolyte': 'Elektrolyt',
    'technology': 'Technologie',
    'membrane': 'Membran',
    'test_type': 'Testtyp',
    'setup_type': 'Prüfebene',
    'synthesis': 'Synthese',
}
NUMERIC_COLUMNS = [
    ('overpotential_at_10_ma_cm2', 'OER η bei 10 mA/cm²', 'mV', 1, True),
    ('cell_voltage_at_1_a_cm2', 'PEM U bei 1 A/cm²', 'V', 3, True),
    ('durability_hours', 'Dauerlauf', 'h', 1, True),
    ('durability_current_density', 'Stromdichte im Dauerlauf', 'A/cm^2', 3, True),
    ('cell_temperature', 'Zelltemperatur', 'degC', 1, True),
    ('electrolyte_temperature', 'Elektrolyttemperatur', 'degC', 1, False),
    ('ph', 'pH', None, 2, False),
    ('catalyst_loading', 'Katalysatorbeladung', 'mg/cm^2', 2, False),
    ('tafel_slope', 'Tafel-Steigung pro Dekade', 'mV', 1, False),
    (
        'charge_transfer_resistance',
        'Ladungsübertragungswiderstand Rct',
        'ohm*cm^2',
        2,
        False,
    ),
    ('mass_activity', 'Massenaktivität', 'A/g', 2, False),
    (
        'capacitance_normalized_activity',
        'Kapazitätsnormierte Aktivität',
        'A/F',
        2,
        False,
    ),
    (
        'double_layer_capacitance_areal',
        'Doppelschichtkapazität (CSV: ECSA)',
        'uF/cm^2',
        1,
        False,
    ),
    ('degradation_rate', 'Degradationsrate', 'uV/h', 1, False),
]
COLUMNS = [
    Column(search_quantity='entry_name', title='Eintrag', selected=True),
    Column(
        search_quantity=field('characterization_methods'),
        title='Charakterisierung',
        selected=True,
    ),
    *(
        Column(
            search_quantity=field(name),
            title=title,
            selected=name in {'catalyst', 'test_type'},
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
    Column(search_quantity=METHODS, title='Messmethoden'),
    Column(search_quantity=field('article_doi'), title='Publikations-DOI'),
]

electrolysis_app = AppEntryPoint(
    name='Electrolysis Gallery',
    description='Search curated electrolysis literature measurements.',
    app=App(
        label='Elektrolyse',
        path='electrolysis',
        resource=ResourceEnum.ENTRIES,
        category='Use Cases',
        description='Literaturdaten zu OER-Halbzellen und PEM-Einzelzellen vergleichen.',
        readme=(
            'Eine Zeile entspricht einem Katalysator in einem Versuchsaufbau. '
            'Die OER- und PEM-Spalten zeigen Werte bei festen Stromdichten. '
            'PEM-Spannungen stammen aus Messungen vor HFR-Korrektur. '
            'Charakterisierung bezieht sich auf das Katalysatormaterial im Paper. '
            'Die Markierung CSV kennzeichnet Angaben mit offener Quellenprüfung. '
            'Weitere Betriebspunkte und Fundstellen stehen im Prüfbericht des Uploads.'
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
        menu=Menu(
            size='lg',
            items=[
                MenuItemTerms(search_quantity=METHODS, title='Messmethoden'),
                MenuItemPeriodicTable(search_quantity=ELEMENTS, title='Elemente'),
                Menu(
                    title='Versuchsaufbau',
                    items=[
                        MenuItemTerms(search_quantity=field(name), title=title)
                        for name, title in CATEGORIES.items()
                    ],
                ),
                Menu(
                    title='Messwerte',
                    items=[
                        MenuItemHistogram(
                            x=Axis(search_quantity=field(name), unit=unit), title=title
                        )
                        for name, title, unit, _, _ in NUMERIC_COLUMNS
                    ],
                ),
                Menu(
                    title='Charakterisierung',
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
