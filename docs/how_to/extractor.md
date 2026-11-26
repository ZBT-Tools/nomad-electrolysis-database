# Literature data extractor

The extractor runs before a NOMAD upload. Use the literature command to extend the gallery CSV from additional publications. Use the archive command to package records from the supported JATS import workflow.

## Extend the gallery CSV

```sh
python -m pip install ".[literature]"
electrolyse-literature gallery.csv --source profile.json article.pdf --output-dir output/literature
```

Repeat `--source PROFILE DOCUMENT` for each publication. The command reads searchable PDFs, JATS XML, and UTF-8 text with optional form-feed page breaks. Keep one column ID per catalyst and experimental setup. Use the same IDs and citation strings on reruns. A conflicting value or citation stops the run before writing new output.

Each JSON profile contains a `source` object with `doi`, `url`, `citation`, version information and a `license` object with `status`, `url` and `location`. It also contains a `samples` list. Each sample has a `column` (such as `#6`), a descriptive `label`, and a `fields` object keyed by the exact CSV row labels. A field rule includes the CSV `unit`, a human-readable `location`, and a Python regular expression `pattern`. For PDF rules, add the one-based `page` to constrain matching. For categorical fields, provide a fixed normalized `value` backed by the match. For numeric fields, capture the number in a group named `value` and provide a `reported_unit` and decimal `factor` if conversion is needed. Use `note` to record relevant conditions, caveats, or uncertainty. The license object also accepts an optional `pattern` and `page` to verify the license notice in the source.

The profile author identifies the setup and checks that each result belongs to the right catalyst, operating point, and unit. Only a unique match populates a registered field. Unmapped fields stay blank. Use a reviewed source table or dataset when an exact number is available. A value read from a plot needs a documented digitization method and an uncertainty or precision estimate before it can be compared with tabulated values.

The output contains a UTF-8 CSV and two review reports. Open the HTML report in a browser to find values by column ID, descriptor, or sample name. It links to the publication and, when a local PDF was supplied, to the relevant page. The JSON report records the original number, unit conversions, source locations, and SHA-256 checksums of the source, profile and CSV. License evidence is recorded per source. The output is for internal review and carries no publication approval.

The `--add-electrode-and-durability-rows` option adds the agreed `Electrode role` and `Durability current density` descriptors when absent. Additional descriptors require an update to the gallery CSV and mappings.

## Build a multi-publication NOMAD upload

```sh
electrolyse-gallery-import gallery-extended.csv gallery-review.json --output-dir output/imports
```

The command checks the CSV against the extraction report and creates one archive per sample column. The Explore ZIP uses the installed Electrolysis schema and requires plugin version 0.4.0 or later. The standalone ZIP embeds the schema and opens through NOMAD's archive parser. Use one ZIP per upload. Both packages include the review and license records and are intended for unpublished testing.

Use `--components` to provide a reviewed JSON object mapping component names to lists of element symbols. If the CSV contains columns from the original JATS workflow, supply the original XML with `--article-xml`. Those columns keep their source-based measurements and conflict checks.

## Build a publication-specific NOMAD upload

```sh
electrolyse-data-extractor "path/to/gallery.csv" --article-xml "path/to/article.xml" --explore
```

Use `--output-dir` to change the destination from the default `output/`. With `--explore`, the generated archives reference the installed plugin schema and are visible in the Explore app. Omitting the flag embeds the schema in the archives for use with NOMAD's built-in archive parser.

This command expects the source gallery CSV for the publication-specific workflow. Its DOI and repository identifier, sample names and matching rules must agree with the inputs.

## How it works

1. **Validate the inputs.** Read the UTF-8 gallery CSV, check the publication label and identify the sample mapped to each column. Verify the source identifiers and an article-level CC BY 4.0 notice in the JATS XML.
2. **Extract published values.** Apply rules to specific XML sections and figure captions. For each match, record the original value, unit and XML location. Missing or ambiguous matches for required extraction rules stop the run.
3. **Reconcile with the gallery.** Match measurements to the CSV fields and normalize units for comparison. The review report preserves disagreements and identifies values carried over solely from the CSV. Characterization fields record whether the method was reported for the catalyst.
4. **Write the import.** Create one flat archive per sample column. The archive contains the gallery fields, relevant operating points and searchable method and element summaries. Detailed evidence stays in the review report.

## Review the output

The output directory contains a ZIP for NOMAD and a standalone JSON review report. The ZIP includes the same report alongside the archives. The report includes per-field checks, original and imported values, XML locations and source checksums. Values carried over solely from the CSV are identified as `csv_only`. Inspect conflicts, unresolved values and the license evidence before using the data. The generated packages are marked `test_only` and intended for unpublished validation uploads.
