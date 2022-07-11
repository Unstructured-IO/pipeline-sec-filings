# Downloading CSV's with all sections extracted for fiings

## Step 1: Download filings from Edgar

Given a list of symbols (tickers or CIK's) and which form type to download in $FILINGS_MANIFEST_FILE, save resulting files and manifest json in $SEC_DOCS_DIR.

```
# needed for Edgar's API
export SEC_API_ORGANIZATION=<your org>
export SEC_API_EMAIL=<your email>

PYTHONPATH=. SEC_DOCS_DIR=sec-filing-downloads \
FILINGS_MANIFEST_FILE=test_utils/symbols-for-validation-csvs.txt \
python test_utils/get_sec_docs_from_edgar.py
```

## Step 2: Generate validation csv's with downloaded files and manifest json

```
PYTHONPATH=. SEC_DOCS_DIR=sec-filing-downloads/ CSV_FILES_DIR=validation-csvs python \
test_utils/create_validation_csv_files.py
```

Note that you may also provide the following env vars in the command above:

* `PIPELINE_SECTION_API_URL` - defaults to local API.
* `FILINGS_MANIFEST_JSON` - the list of filings to create CSV's for. defaults to $SEC_DOCS_DIR/sec_docs_manifest.json which is written step 1.
