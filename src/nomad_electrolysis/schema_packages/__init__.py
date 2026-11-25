"""Lazy entry point for the installed archive schema."""

from nomad.config.models.plugins import SchemaPackageEntryPoint


class ElectrolysisSchemaEntryPoint(SchemaPackageEntryPoint):
    def load(self):
        from nomad_electrolysis.schema import m_package

        return m_package


electrolysis_schema = ElectrolysisSchemaEntryPoint(
    name='Electrolysis schema',
    description='Literature measurements and comparison quantities for the Electrolysis Gallery.',
)
