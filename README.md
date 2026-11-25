# NOMAD Electrolysis Database

A NOMAD 2.0 plugin for exploring curated electrolysis literature data. The Explore app filters by elements, electrochemical methods, electrolyte, setup and characterization. Each sample and experimental setup has a flat archive entry. The Chanda example has four entries, with the durability current density beside the test duration. The extractor writes original values, units, license evidence and source locations to a separate review report.

## Development

```sh
uv sync --extra dev
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run mkdocs build --strict
uv build
```

The development extra uses NOMAD 2.0.0, the version used by the ZBT test Oasis.

## Create the Chanda import

The extractor takes the Chanda gallery CSV and the version-of-record JATS XML. Download the XML from the [PMC open-access archive](https://pmc-oa-opendata.s3.amazonaws.com/PMC13533152.1/PMC13533152.1.xml). Pass both files to the installed command:

```sh
uv run electrolyse-data-extractor gallery.csv --article-xml chanda_2026.jats.xml --explore
```

Upload `output/chanda-2026-explore.zip` to an unpublished project after installing the plugin. Open **Explore → Use Cases → Elektrolyse**. To generate self-contained archives for NOMAD's built-in archive parser, omit `--explore`. The source check is specific to Chanda et al. ([paper and CC BY 4.0 notice](https://pmc.ncbi.nlm.nih.gov/articles/PMC13533152/)).

## Install on the ZBT test Oasis

In the Oasis distribution, add the plugin to the `plugins` extra in `pyproject.toml`, pinning the tested Git revision:

```toml
"nomad-electrolysis-database @ git+https://github.com/ZBT-Tools/nomad-electrolysis-database.git@<COMMIT-SHA>",
```

Replace any previous `nomad-electrolysis` wheel dependency and its local source override. Both distributions expose the same Python import path and schema identity. Run `uv lock`, build the test image from the `for_plugin_test` branch, and roll out its `app` and `worker` services. If the Oasis uses a plugin allowlist, enable `nomad_electrolysis.apps:electrolysis_app` and `nomad_electrolysis.schema_packages:electrolysis_schema`.

## Licenses

The plugin code uses the Apache License 2.0. The Chanda paper uses CC BY 4.0. The full text and generated import packages are supplied separately. The extractor records publication and license provenance, and its output is marked for the test Oasis.
