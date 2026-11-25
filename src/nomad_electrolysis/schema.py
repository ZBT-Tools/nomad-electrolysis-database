"""Installed version of the metainfo used by the archive exporter."""

from nomad.metainfo import SchemaPackage

from .definitions import archive_definitions

definitions = archive_definitions()
definitions['name'] = __name__
m_package = SchemaPackage.m_from_dict(definitions)
m_package.__init_metainfo__()
ElectrolysisRecord = m_package.all_definitions['ElectrolysisRecord'].section_cls
