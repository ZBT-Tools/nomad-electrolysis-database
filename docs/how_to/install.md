# Install and use the plugin

The plugin requires Python 3.11 or later and NOMAD 2.x. Install both plugin entry points in the NOMAD environment that serves the Explore app and processes uploads.

## Install into an existing NOMAD environment

Install from Git:

```sh
python -m pip install "nomad-electrolysis-database @ git+https://github.com/ZBT-Tools/nomad-electrolysis-database.git"
```

Use a tested tag or commit to pin a Git installation. If you have a built wheel, install it by passing its path:

```sh
python -m pip install "path/to/plugin.whl"
```

## Add the plugin to a container-based NOMAD distribution

Add the package to the distribution dependency group installed by the NOMAD image. For a distribution that uses a `plugins` extra, add the following entry to that list and replace `<COMMIT-SHA>` with the tested revision:

```toml
"nomad-electrolysis-database @ git+https://github.com/ZBT-Tools/nomad-electrolysis-database.git@<COMMIT-SHA>",
```

Update the distribution lockfile, build the image and roll it out to the application and processing workers. See the [NOMAD Oasis configuration guide](https://docs.nomad-lab.eu/develop/howto/oasis/configure.html#plugins).

NOMAD discovers installed plugin entry points automatically. If the distribution restricts enabled entry points, include both of the following in its existing configuration:

- `nomad_electrolysis.apps:electrolysis_app`
- `nomad_electrolysis.schema_packages:electrolysis_schema`

## Import and explore

1. Prepare an import package in Explore mode using the [literature data extractor](extractor.md).
2. Upload the ZIP to an unpublished NOMAD project and wait for processing to finish.
3. Open **Explore → Use Cases → Electrolysis**. Use the method and element filters to find entries and compare their performance and operating points.
4. Open the review JSON in the project's files to inspect source locations, unit conversions and input conflicts.
