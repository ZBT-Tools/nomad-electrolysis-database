# Installation and import

Install the plugin in the NOMAD 2.0 distribution and deploy that environment to both the app and worker. The [repository README](https://github.com/ZBT-Tools/nomad-electrolysis-database#install-on-the-zbt-test-oasis) lists the Git dependency and entry points for the ZBT test Oasis.

Generate the Chanda example with the gallery CSV and the [licensed JATS full text](https://pmc-oa-opendata.s3.amazonaws.com/PMC13533152.1/PMC13533152.1.xml):

```sh
uv run electrolyse-data-extractor gallery.csv --article-xml chanda_2026.jats.xml --explore
```

Upload the Explore ZIP to an unpublished project. Once processing completes, open **Explore → Use Cases → Elektrolyse**. The four entries include a PEM durability result of 380 h at 0.4 A/cm². The review JSON in the upload provides provenance for the extracted values.
