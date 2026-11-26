# NOMAD Electrolysis Database

A [NOMAD](https://nomad-lab.eu/) plugin for exploring curated electrolysis literature data. Each entry represents a catalyst under a specific experimental setup.

## Features

- **Schema package** for experimental conditions, comparable performance indicators and characterization method flags
- **Explore app** with filters for elements, electrochemical methods, experimental setups and characterization
- **Literature data extractor** that prepares archive uploads and records source locations, original values, unit conversions and license evidence in a review report

## Installation

The plugin requires Python 3.11 or later and NOMAD 2.x. Install it from Git into the Python environment used by NOMAD.

```sh
python -m pip install "nomad-electrolysis-database @ git+https://github.com/ZBT-Tools/nomad-electrolysis-database.git"
```

For a reproducible deployment, pin a tested tag or commit. On a container-based installation, include the package in the NOMAD distribution and rebuild the image used by the application and processing workers. See the [installation guide](docs/how_to/install.md) for package configuration, entry points and import steps.

## Usage

Open **Explore → Use Cases → Elektrolyse** to browse entries. Use the periodic table or method filters to narrow the results, and compare measurements at the operating points shown in the column headings.

The [extractor guide](docs/how_to/extractor.md) describes required inputs, supported sources and the contents of the generated archives and review report.

## Development

```sh
uv sync --extra dev
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run mkdocs build --strict
uv build
```

The development environment tests against NOMAD 2.0.0. See the [NOMAD plugin development guidelines](https://docs.nomad-lab.eu/develop/howto/plugins/plugins.html#plugin-development-guidelines) for packaging and contribution conventions.

## License

The plugin code is distributed under the [Apache License 2.0](LICENSE). Source publications and data retain their associated licenses.
