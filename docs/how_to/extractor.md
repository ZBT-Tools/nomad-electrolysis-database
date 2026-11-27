# Literature data extractor

The extractor runs before a NOMAD upload. Use the literature command to extend the gallery CSV from additional publications. Use the archive command to package records from the supported JATS import workflow.

## Extend the gallery CSV

```sh
python -m pip install ".[literature]"
electrolyse-literature gallery.csv --source profile.json article.pdf --output-dir output/literature
```

Repeat `--source PROFILE DOCUMENT` for each publication. The command reads searchable PDFs, JATS XML, and UTF-8 text with optional form-feed page breaks. Keep one column ID per catalyst and experimental setup. Use the same IDs and citation strings on reruns. A conflicting value or citation stops the run before writing new output.

Each JSON profile contains a `source` object with `doi`, `url`, `citation`, version information and a `license` object with `status`, `url` and `location`. It also contains a `samples` list. Each sample has a `column` (such as `#6`), a descriptive `label`, and a `fields` object keyed by the exact CSV row labels. A field rule includes the CSV `unit`, a human-readable `location`, and a Python regular expression `pattern`. For PDF rules, add the one-based `page` to constrain matching. For categorical fields, provide a fixed normalized `value` backed by the match. For numeric fields, capture the number in a group named `value` and provide a `reported_unit` and decimal `factor` if conversion is needed. Use `note` to record relevant conditions, caveats, or uncertainty. The license object also accepts an optional `pattern` and `page` to verify the license notice in the source.

Numeric rules may also specify an `offset` in the CSV unit. The extractor adds the offset after multiplication and records both operations in the JSON report. Use the note to state the reference and assumptions for derived values.

The profile author identifies the setup and checks that each result belongs to the right catalyst, operating point, and unit. Only a unique match populates a registered field. Unmapped fields stay blank. Use a reviewed source table or dataset when an exact number is available. A value read from a plot needs a documented digitization method and an uncertainty or precision estimate before it can be compared with tabulated values.

The output contains a UTF-8 CSV and two review reports. Open the HTML report in a browser to find values by column ID, descriptor, or sample name. It links to the publication and, when a local PDF was supplied, to the relevant page. The JSON report records the original number, unit conversions, source locations, and SHA-256 checksums of the source, profile and CSV. License evidence is recorded per source. The output is for internal review and carries no publication approval.

The `--add-electrode-and-durability-rows` option adds the agreed `Electrode role` and `Durability current density` descriptors when absent. Additional descriptors require an update to the gallery CSV and mappings.

## Build one NOMAD upload per publication

```sh
electrolyse-gallery-import gallery-extended.csv gallery-review.json --output-dir output/imports
```

The command checks the CSV against the extraction report, creates one archive per sample column, and groups the archives by DOI. Each DOI produces one ZIP with its own source review and license evidence. ZIP filenames are based on the DOI and remain stable when the records for that DOI are updated. Keep publications in separate NOMAD uploads so that each paper can be updated and reviewed for publication independently.

The default Explore ZIPs use the installed Electrolysis schema and require plugin version 0.4.0 or later on the target instance. Use `--standalone` to produce one ZIP per DOI with the schema embedded. The export also writes a combined JSON review for local evaluation. All packages are marked `test_only`. Review the license evidence and any supplementary sources before publishing an upload.

Use `--components` to provide a reviewed JSON object mapping component names to lists of element symbols. If the CSV contains columns from the original JATS workflow, supply the original XML with `--article-xml`. The extractor keeps source-supported values and lists omitted CSV values and any explicitly documented estimates in the review report.

## Build a publication-specific NOMAD upload

```sh
electrolyse-data-extractor "path/to/gallery.csv" --article-xml "path/to/article.xml" --explore
```

Use `--output-dir` to change the destination from the default `output/`. With `--explore`, the generated archives reference the installed plugin schema and are visible in the Explore app. Omitting the flag embeds the schema in the archives for use with NOMAD's built-in archive parser.

This command expects the source gallery CSV for the publication-specific workflow. Its DOI and repository identifier, sample names and matching rules must agree with the inputs.

## How it works

1. **Validate the inputs.** Read the UTF-8 gallery CSV, check the publication label and identify the sample mapped to each column. Verify the source identifiers and an article-level CC BY 4.0 notice in the JATS XML.
2. **Extract published values.** Apply rules to specific XML sections and figure captions. For each match, record the original value, unit and XML location. Missing or ambiguous matches for required extraction rules stop the run.
3. **Reconcile with the gallery.** Match measurements to the CSV fields and normalize units for comparison. The review records disagreements, omitted values, and any documented estimates. Characterization fields record methods reported for the catalyst.
4. **Write the import.** Create one flat archive per sample column. The archive contains the gallery fields, relevant operating points and searchable method and element summaries. Detailed evidence stays in the review report.

## Review the output

For the publication-specific command, the output directory contains a ZIP for NOMAD and a separate copy of the JSON review inside that ZIP. The review includes per-field checks, original and imported values, XML locations, and source checksums.
