"""
Downloads example SEC filings from the SEC EDGAR API as specified by examples.json.
Not normally intended to be called by users as it hits EDGAR directly.
Filings for testing/CI instead will be downloaded from s3.
"""
import json
import os
import re
from pathlib import Path


from prepline_sec_filings.fetch import (
    get_filing,
    get_recent_acc_by_cik,
    get_recent_cik_and_acc_by_ticker,
)


SEC_DOCS_DIR = os.environ.get("SEC_DOCS_DIR", "sample-sec-docs")
SEC_API_ORGANIZATION = os.environ.get("SEC_API_ORGANIZATION")
SEC_API_EMAIL = os.environ.get("SEC_API_EMAIL")
# only 1 of these 2 manifests types determines what gets downloaded
FILINGS_MANIFEST_JSON = os.path.join("test_utils", "examples.json")
FILINGS_MANIFEST_FILE = os.environ.get("FILINGS_MANIFEST_FILE")


def fetch_filing_xbrl(ticker, form_type, cik, accession_number, skip_fetch_if_file_exists=True):
    "Fetch a single filing from edgar and write it to $SEC_DOCS_DIR"
    _doc_name = f"{ticker}-{form_type}-{cik}-{accession_number}.xbrl".replace("/", "")
    sec_doc_filename = os.path.join(SEC_DOCS_DIR, _doc_name)
    if skip_fetch_if_file_exists and Path(sec_doc_filename).is_file():
        print(f"skipping download since {sec_doc_filename} exists")
        return

    text = get_filing(cik, accession_number, SEC_API_ORGANIZATION, SEC_API_EMAIL)
    with open(sec_doc_filename, "w+") as f:
        f.write(text)


def parse_examples_json():
    with open(FILINGS_MANIFEST_JSON, "r") as f:
        manifest_json_obj = json.load(f)
    return manifest_json_obj


def parse_manifest_text_file():
    ticker_form_type_pairs = []
    with open(FILINGS_MANIFEST_FILE, "r") as f:
        for line in f.readlines():
            line = line.strip()
            if line and not line.startswith("#"):
                m = re.match(r"(\w+)\s+(\S+)\s*", line)
                ticker_form_type_pairs.append(m.groups())
    return ticker_form_type_pairs


def fetch_filings(manifest_json_obj):
    """Given json like:
      {
        "mmm": {
          "cik": "66740",
          "forms": {
            "10-Q": "000006674022000065"
          }
        },
    download the indicated xbrl documents from edgar.
    """
    for ticker, filing_info in manifest_json_obj.items():
        cik = filing_info["cik"]
        for form_type, accession_number in filing_info["forms"].items():
            fetch_filing_xbrl(ticker, form_type, cik, accession_number)
            print(f"fetched {ticker}")


def get_sample_docs():
    """Fetch filings from edgar ultimately to be used for 'make test-sample-docs'."""
    fetch_filings(parse_examples_json())


def _add_to_manifest_json_obj(manifest_json_obj, ticker, form_type, cik, acc_num):
    if ticker not in manifest_json_obj:
        manifest_json_obj[ticker] = {"forms": {}}
    if cik in manifest_json_obj[ticker]:
        assert manifest_json_obj[ticker]["cik"] == cik
    else:
        manifest_json_obj[ticker]["cik"] = cik
    manifest_json_obj[ticker]["forms"][form_type] = acc_num


def get_latest_docs():
    """Fetch filings from edgar, but unlike get_sample_docs() the
    acession_number and cik that correspond to the most recent filing are
    determined at runtime."""

    manifest_json_obj = {}
    for ticker_or_cik, _form_type in parse_manifest_text_file():
        ticker_or_cik = ticker_or_cik.lower()
        _form_type = _form_type.upper()  # just following the convention :)
        print(f"{ticker_or_cik}-{_form_type}...", end="", flush=True)
        if re.search(r"^\d+$", ticker_or_cik):
            cik = ticker_or_cik
            acc_num, form_type = get_recent_acc_by_cik(cik, _form_type)
        else:
            ticker = ticker_or_cik
            cik, acc_num, form_type = get_recent_cik_and_acc_by_ticker(ticker, _form_type)
        _add_to_manifest_json_obj(manifest_json_obj, ticker_or_cik, form_type, cik, acc_num)
        fetch_filing_xbrl(ticker_or_cik, form_type, cik, acc_num)

    with open(os.path.join(SEC_DOCS_DIR, "sec_docs_manifest.json"), "w") as f:
        json.dump(manifest_json_obj, f, indent=2)


if __name__ == "__main__":
    if SEC_API_ORGANIZATION is None or SEC_API_EMAIL is None:
        raise RuntimeError(
            "Environment vaiables SEC_API_ORGANIZATION and SEC_API_EMAIL "
            "must be set for SEC EDGAR API call (allows them to identify the consumer)"
        )
    Path(SEC_DOCS_DIR).mkdir(exist_ok=True)

    if not FILINGS_MANIFEST_FILE:
        # documents related to python tests in test_real_docs/
        print("env var FILINGS_MANIFEST_FILE not defined, fetching docs for python tests")
        get_sample_docs()
    else:
        # pull latest filings in FILINGS_MANIFEST_FILE for reasons beknownst to user
        get_latest_docs()
