# Literature data extractor

The extractor is a command-line tool that runs before the NOMAD upload. It takes a curated gallery CSV and the corresponding full-text article in JATS XML. The CSV identifies the samples and setup types. The XML supplies the published measurements and evidence for their provenance.

## Run the extractor

```sh
electrolyse-data-extractor "path/to/gallery.csv" --article-xml "path/to/article.xml" --explore
```

Use `--output-dir` to change the destination from the default `output/`. With `--explore`, the generated archives reference the installed plugin schema and are visible in the Explore app. Omitting the flag embeds the schema in the archives for use with NOMAD's built-in archive parser.

The current release implements one publication-specific extraction profile. Its DOI and repository identifier, sample names and matching rules must agree with the inputs. Supporting another article requires a corresponding profile and extraction rules.

## How it works

1. **Validate the inputs.** Read the UTF-8 gallery CSV, check the publication label and identify the sample mapped to each column. Verify the source identifiers and an article-level CC BY 4.0 notice in the JATS XML.
2. **Extract published values.** Apply rules to specific XML sections and figure captions. For each match, record the original value, unit and XML location. Missing or ambiguous matches for required extraction rules stop the run.
3. **Reconcile with the gallery.** Match measurements to the CSV fields and normalize units for comparison. The review report preserves disagreements and identifies values carried over solely from the CSV. Characterization fields record whether the method was reported for the catalyst.
4. **Write the import.** Create one flat archive per sample column. The archive contains the gallery fields, relevant operating points and searchable method and element summaries. Detailed evidence stays in the review report.

## Review the output

The output directory contains a ZIP for NOMAD and a standalone JSON review report. The ZIP includes the same report alongside the archives. The report includes per-field checks, original and imported values, XML locations and source checksums. Values carried over solely from the CSV are identified as `csv_only`. Inspect conflicts, unresolved values and the license evidence before using the data. The generated packages are marked `test_only` and intended for unpublished validation uploads.
