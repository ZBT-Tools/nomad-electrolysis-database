import pytest

from nomad_electrolysis.definitions import SCHEMA_NAME
from nomad_electrolysis.gallery_import import REVIEW_NAME, publication_packages


@pytest.mark.parametrize('standalone', [False, True])
def test_each_upload_contains_only_one_publication_and_its_review(standalone):
    licenses = {'10.1000/one': 'CC BY 4.0', '10.1000/two': 'CC BY-NC 4.0'}
    sources = [
        {'doi': doi, 'license': {'status': license}}
        for doi, license in licenses.items()
    ]
    archives = {
        f'{index}.archive.json': {
            'data': {
                'article_doi': doi,
                'article_license': license,
                'm_def': SCHEMA_NAME,
            },
        }
        for index, (doi, license) in enumerate(licenses.items(), 1)
    }
    review = {'sources': sources, 'cells': [{'doi': doi} for doi in licenses]}

    packages = publication_packages(archives, review, {}, standalone=standalone)

    assert len(packages) == len(licenses)
    for files in packages.values():
        report = files[REVIEW_NAME]
        (source,) = report['sources']
        doi = source['doi']
        assert report['cells'] == [{'doi': doi}]
        assert report['entry_count'] == 1
        (archive,) = [item for name, item in files.items() if name != REVIEW_NAME]
        assert archive['data']['article_doi'] == doi
        assert archive['data']['article_license'] == licenses[doi]
        assert ('definitions' in archive) == standalone
    assert all('definitions' not in archive for archive in archives.values())
