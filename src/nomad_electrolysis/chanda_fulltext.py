"""Extract the gallery measurements from the Chanda JATS full text."""

import hashlib
import re
from datetime import UTC, datetime
from xml.etree import ElementTree

FULLTEXT_URL = (
    'https://pmc-oa-opendata.s3.amazonaws.com/PMC13533152.1/PMC13533152.1.xml'
)
CC_BY_URL = 'https://creativecommons.org/licenses/by/4.0/'
XLINK_HREF = '{http://www.w3.org/1999/xlink}href'
DASHES = str.maketrans('‐‑–−', '----')
NUM = r'\d+(?:\.\d+)?'
RESULTS = "./body/sec[@id='smsc70388-sec-0002']/p"
CONCLUSION = "./body/sec[@id='smsc70388-sec-0003']/p"
ABSTRACT = './front/article-meta/abstract[1]/p'
FIGURE_2 = ".//fig[@id='smsc70388-fig-0002']/caption/p"
FIGURE_3 = ".//fig[@id='smsc70388-fig-0003']/caption/p"


def normalized_text(element):
    return ' '.join(''.join(element.itertext()).translate(DASHES).split())


def license_evidence(root, article, payload, doi):
    meta = root.find('./front/article-meta')
    if root.tag != 'article' or meta is None or root.find('./body') is None:
        raise ValueError('Expected a complete JATS article.')
    ids = {node.get('pub-id-type'): node.text for node in meta.findall('article-id')}
    if ids.get('doi') != doi or ids.get('pmcid') != 'PMC13533152':
        raise ValueError('Unexpected DOI or PMCID in the full text.')
    # Require the article-level public notice. A separate ALI text-mining
    # license reference or a link from a bibliography is insufficient.
    for index, notice in enumerate(meta.findall('./permissions/license/license-p'), 1):
        for link in notice.findall('.//ext-link'):
            href = link.get(XLINK_HREF, '').replace('http://', 'https://', 1)
            if href.rstrip('/') == CC_BY_URL.rstrip('/'):
                return {
                    **article,
                    'license': 'CC-BY-4.0',
                    'license_url': CC_BY_URL,
                    'status': 'verified',
                    'evidence_location': f'./front/article-meta/permissions/license/license-p[{index}]/ext-link',
                    'verified_at': datetime.now(UTC).isoformat(timespec='seconds'),
                    'pmcid': ids['pmcid'],
                    'pmc_version': ids.get('pmcid-ver'),
                    'fulltext_url': FULLTEXT_URL,
                    'fulltext_sha256': hashlib.sha256(payload).hexdigest(),
                    'processing': 'Measurements extracted from JATS text and normalized. Article and figures are not packaged.',
                }
    raise ValueError('No article-level CC BY 4.0 notice found in the JATS permissions.')


def capture(root, scope, pattern, label):
    matches = []
    for index, paragraph in enumerate(root.findall(scope), 1):
        for match in re.finditer(pattern, normalized_text(paragraph)):
            matches.append((match, f'{scope}[{index}]'))
    if len(matches) != 1:
        raise ValueError(
            f'Expected one full-text match for {label}, found {len(matches)}.'
        )
    return matches[0]


def characterization_presence(root):
    rules = {
        'XPS': (
            FIGURE_2,
            r'XPS and XAS characterizations of the three electrocatalysts',
        ),
        'XRD': (
            RESULTS,
            r'three as-prepared catalysts, powder X-ray diffraction \(P-XRD\)',
        ),
        'SEM': (
            RESULTS,
            r'prepared electrocatalysts were investigated using scanning electron microscopy \(SEM\)',
        ),
        'TEM': (
            RESULTS,
            r'Transmission electron microscopy \(TEM\) images reveal that all three samples',
        ),
        'XAS in-situ': (
            RESULTS,
            r'Upon electrolyte circulation, all samples exhibit an increase in Mn valence',
        ),
    }
    methods = {}
    for label, (scope, pattern) in rules.items():
        _, locator = capture(root, scope, pattern, label)
        methods[label] = {
            'present': True,
            'status': 'verified',
            'source_locator': locator,
            'note': 'Reported for the catalyst material in the article.',
        }
    _, dry_locator = capture(
        root, RESULTS, r'XANES spectra of dry MnO2, MnO2-Nb, and MnO2-Nb-F', 'dry XAS'
    )
    methods['XAS ex-situ'] = {
        'present': None,
        'status': 'review',
        'source_locator': dry_locator,
        'note': 'Dry XANES is reported. The main text does not establish whether it was measured outside the operando setup. The CSV flag is retained.',
    }
    _, icp_locator = capture(
        root,
        RESULTS,
        r'the electrolyte was analyzed by ICP-OES',
        'ICP analytical method',
    )
    methods['ICP-MS'] = {
        'present': False,
        'status': 'not_reported',
        'source_locator': icp_locator,
        'note': 'The main article reports ICP-OES for the half-cell electrolyte. ICP-MS is not reported.',
    }
    for label in ('Raman in-situ', 'Raman ex-situ'):
        methods[label] = {
            'present': False,
            'status': 'not_reported',
            'source_locator': None,
            'note': 'No Raman characterization for the catalyst is reported in the checked main article.',
        }
    return methods


def extract_fulltext(payload, evidence):
    try:
        root = ElementTree.fromstring(payload)
    except ElementTree.ParseError as error:
        raise ValueError(f'Cannot parse the article XML: {error}') from error
    article = next(
        source for source in evidence['sources'] if source['id'] == 'article'
    )
    verified_article = license_evidence(root, article, payload, evidence['doi'])

    overpotential, overpotential_path = capture(
        root,
        RESULTS,
        rf'At a current density of ({NUM}) mA cm-2, the MnO2-Nb-F catalyst exhibits the lowest '
        rf'overpotential of ({NUM}) ± ({NUM}) V, compared to ({NUM}) ± ({NUM}) V for MnO2-Nb '
        rf'and ({NUM}) ± ({NUM}) V for pristine MnO2\.',
        'half-cell overpotential triplet',
    )
    tafel, tafel_path = capture(
        root,
        RESULTS,
        rf'MnO2-Nb-F exhibits a lower slope \(({NUM}) mV dec-1\) compared to '
        rf'MnO2 \(({NUM}) mV dec-1\) and MnO2-Nb \(({NUM}) mV dec-1\)',
        'Tafel slopes',
    )
    eis, eis_path = capture(
        root,
        RESULTS,
        rf'EIS analysis was carried out at ({NUM}) V \(vs\. (RHE)\) '
        rf'in the electrolyte solution of ({NUM}) M H2SO4',
        'half-cell EIS conditions',
    )
    rct, rct_path = capture(
        root,
        RESULTS,
        rf'MnO2-Nb-F electrode achieves the lowest charge transfer resistance \(R\s*ct ≈ ({NUM}) Ω cm2\)'
        rf'[^.]*\. The MnO2-Nb electrode exhibits a moderate R\s*ct of ({NUM}) Ω cm2, '
        rf'while pristine MnO2 displays the highest R\s*ct of ({NUM}) Ω cm2',
        'charge-transfer resistances',
    )
    capacitance, capacitance_path = capture(
        root,
        RESULTS,
        rf'linear fits yield C\s*dl values of ({NUM}) mF cm-2 for MnO2, '
        rf'({NUM}) mF cm-2 for MnO2-Nb, and ({NUM}) mF cm-2 for MnO2-Nb-F\.',
        'areal double-layer capacitances',
    )
    activity_point, activity_path = capture(
        root,
        RESULTS,
        rf'specific and mass activities were evaluated at an overpotential of ({NUM}) mV',
        'half-cell activity operating point',
    )
    specific, specific_path = capture(
        root,
        RESULTS,
        rf'specific activity increases from ({NUM}) A F-1 for MnO2 to '
        rf'({NUM}) A F-1 for MnO2-Nb and further to ({NUM}) A F-1 for MnO2-Nb-F\.',
        'capacitance-normalized activities',
    )
    mass, mass_path = capture(
        root,
        RESULTS,
        rf'mass activity which increases from ({NUM}) A g-1 \(MnO2\) to '
        rf'({NUM}) A g-1 \(MnO2-Nb\) and ({NUM}) A g-1 \(MnO2-Nb-F\)',
        'mass activities',
    )
    halfcell_duration, halfcell_path = capture(
        root,
        RESULTS,
        rf'chronopotentiometry \(CP\) was performed for MnO2, MnO2-Nb, MnO2-Nb-F, '
        rf'and the IrO x benchmark at a constant current density of ({NUM}) mA cm-2 '
        rf'in ({NUM}) M H2SO4 for ({NUM}) h',
        'half-cell duration and current density',
    )
    halfcell_drift, halfcell_drift_path = capture(
        root,
        RESULTS,
        rf'MnO2-Nb-F exhibits the most stable behavior[^.]*'
        rf'stabilizing at {NUM} V .*? corresponding to a decay rate of ({NUM}) mV h-1',
        'co-doped half-cell degradation rate',
    )
    polarization, polarization_path = capture(
        root,
        RESULTS,
        rf'MnO2-Nb-F electrode achieves ({NUM}) A cm-2 at ({NUM}) V',
        'PEM polarization point',
    )
    _, correction_path = capture(
        root,
        RESULTS,
        r'Prior to HFR correction \(Figure 4a\)',
        'PEM voltage correction',
    )
    pem_duration, pem_duration_path = capture(
        root,
        ABSTRACT,
        rf'operational stability for ({NUM}) h at ({NUM}) A cm-2',
        'PEM duration and current density',
    )
    pem_drift, pem_drift_path = capture(
        root,
        CONCLUSION,
        rf'average degradation rate of the MnO2-Nb-F electrode \(({NUM}) mV h-1\)',
        'average PEM degradation rate',
    )
    pem_setup, pem_setup_path = capture(
        root,
        ABSTRACT,
        rf'integrated into a PEM electrolyzer \(({NUM}) cm2, ({NUM}) °C\)',
        'PEM area and temperature',
    )
    scan, scan_path = capture(
        root,
        FIGURE_3,
        rf'Averaged LSV curves recorded at ({NUM}) mV s-1',
        'LSV scan rate',
    )

    extracted = {
        'overpotential': (
            overpotential,
            overpotential_path,
            {'#1': 2, '#4': 4, '#5': 6},
            {'current_density': float(overpotential[1]) / 1000},
            overpotential_path,
        ),
        'tafel_slope': (tafel, tafel_path, {'#1': 1, '#4': 3, '#5': 2}, {}, None),
        'charge_transfer_resistance': (
            rct,
            rct_path,
            {'#1': 1, '#4': 2, '#5': 3},
            {'electrode_potential': float(eis[1]), 'potential_scale': eis[2]},
            eis_path,
        ),
        'double_layer_capacitance_areal': (
            capacitance,
            capacitance_path,
            {'#1': 3, '#4': 2, '#5': 1},
            {},
            None,
        ),
        'mass_activity': (
            mass,
            mass_path,
            {'#1': 3, '#4': 2, '#5': 1},
            {'operating_overpotential': float(activity_point[1])},
            activity_path,
        ),
        'capacitance_normalized_activity': (
            specific,
            specific_path,
            {'#1': 3, '#4': 2, '#5': 1},
            {'operating_overpotential': float(activity_point[1])},
            activity_path,
        ),
        'halfcell_duration': (
            halfcell_duration,
            halfcell_path,
            {'#1': 3, '#4': 3, '#5': 3},
            {'current_density': float(halfcell_duration[1]) / 1000},
            halfcell_path,
        ),
        'electrode_potential_drift_rate': (
            halfcell_drift,
            halfcell_drift_path,
            {'#1': 1},
            {'current_density': float(halfcell_duration[1]) / 1000},
            halfcell_path,
        ),
        'cell_voltage': (
            polarization,
            polarization_path,
            {'#2': 2},
            {
                'current_density': float(polarization[1]),
                'voltage_correction': 'before_HFR_correction',
            },
            correction_path,
        ),
        'pem_duration': (
            pem_duration,
            pem_duration_path,
            {'#2': 1},
            {'current_density': float(pem_duration[2])},
            pem_duration_path,
        ),
        'cell_voltage_drift_rate': (
            pem_drift,
            pem_drift_path,
            {'#2': 1},
            {'current_density': float(pem_duration[2])},
            pem_duration_path,
        ),
    }
    evidence['sources'] = [
        verified_article if source['id'] == 'article' else source
        for source in evidence['sources']
    ]
    evidence['extraction_method'] = 'chanda_jats_rules_v1'
    evidence['characterization'] = characterization_presence(root)
    evidence['setups']['oer_half_cell']['electrolyte_concentration'] = float(eis[3])
    evidence['setups']['oer_half_cell']['setup_numeric_locator'] = eis_path
    evidence['setups']['pem_single_cell'].update(
        active_area=float(pem_setup[1]),
        cell_temperature=float(pem_setup[2]),
        setup_numeric_locator=pem_setup_path,
    )
    evidence['methods']['lsv'].update(
        scan_rate=float(scan[1]), method_locator=scan_path
    )

    for series in evidence['series']:
        rule = series.get('rule', series['quantity'])
        match, locator, groups, conditions, condition_locator = extracted[rule]
        series.update(
            values={column: float(match[group]) for column, group in groups.items()},
            source_literals={column: match[group] for column, group in groups.items()},
            source_locator=locator,
            conditions=conditions,
        )
        if condition_locator:
            series['condition_locator'] = condition_locator
        if rule == 'overpotential':
            series['uncertainties'] = {
                column: float(match[group + 1]) for column, group in groups.items()
            }
    return evidence
