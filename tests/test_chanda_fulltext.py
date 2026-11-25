import hashlib
from xml.etree import ElementTree

import pytest

from nomad_electrolysis.chanda_fulltext import CC_BY_URL, license_evidence

DOI = '10.1002/smsc.70388'


def test_license_evidence_is_read_from_article_permissions():
    payload = f"""
    <article xmlns:xlink="http://www.w3.org/1999/xlink">
      <front><article-meta>
        <article-id pub-id-type="doi">{DOI}</article-id>
        <article-id pub-id-type="pmcid">PMC13533152</article-id>
        <permissions><license><license-p>
          <ext-link xlink:href="{CC_BY_URL}">CC BY 4.0</ext-link>
        </license-p></license></permissions>
      </article-meta></front>
      <body><sec><p>Synthetic fixture.</p></sec></body>
    </article>
    """.encode()
    evidence = license_evidence(ElementTree.fromstring(payload), {}, payload, DOI)
    assert evidence['license'] == 'CC-BY-4.0'
    assert evidence['fulltext_sha256'] == hashlib.sha256(payload).hexdigest()

    changed = payload.replace(b'/by/4.0/', b'/by-nc/4.0/')
    with pytest.raises(ValueError, match='No article-level CC BY 4.0 notice'):
        license_evidence(ElementTree.fromstring(changed), {}, changed, DOI)
