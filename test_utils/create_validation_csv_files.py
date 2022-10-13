"""Given an $SEC_DOCS_DIR with a sec_docs_manifest.json file, create
a CSV with all extracted sections, one row per section."""
import json
import os
import subprocess
from pathlib import Path
import time

import pandas as pd


from prepline_sec_filings.fetch import archive_url
from prepline_sec_filings.sections import SECTIONS_10K, SECTIONS_10Q, SECTIONS_S1
from prepline_sec_filings.sec_document import SECDocument
from unstructured_api_tools.pipelines.api_conventions import get_pipeline_path


SEC_DOCS_DIR = os.environ.get("SEC_DOCS_DIR")
CSV_FILES_DIR = os.environ.get("CSV_FILES_DIR")
FILINGS_MANIFEST_JSON = os.environ.get(
    "FILINGS_MANIFEST_JSON", os.path.join(SEC_DOCS_DIR, "sec_docs_manifest.json")
)
PIPELINE_SECTION_API_URL = os.environ.get(
    "PIPELINE_SECTION_API_URL", f"http://127.0.0.1:8000{get_pipeline_path('section')}"
)


def _fetch_response_from_api_curl(sec_doc_filename):
    time.sleep(1)
    command = [
        "curl",
        "-s",
        f"{PIPELINE_SECTION_API_URL}",
        "-H",
        "Accept: application/json",
        "-H",
        "Content-Type: multipart/form-data",
        "-F",
        f"file=@{sec_doc_filename}",
        "-F",
        "section=_ALL",
    ]
    proc = subprocess.run(command, capture_output=True)

    resp_data = {}
    if proc.returncode != 0:
        print(f"Failed to get results for {sec_doc_filename}", flush=True)
        print(proc.stderr)
    else:
        try:
            resp_data = json.loads(proc.stdout.decode("utf-8"))
            if "error" in resp_data:
                print(f"Error in response for api for {sec_doc_filename}", flush=True)
                print(resp_data)
                resp_data = {}
        except json.decoder.JSONDecodeError:
            print(f"failed to create json obj from the response for {command}")
    return resp_data


def parse_manifest_json():
    with open(FILINGS_MANIFEST_JSON, "r") as f:
        manifest_json_obj = json.load(f)
    return manifest_json_obj


def _bookkeeping_info(keys, values, ticker_or_cik, cik, acc_num):
    """Add convenience lookup keys/values to row."""
    keys.append("url_for_xbrl")
    values.append(archive_url(cik, acc_num))
    keys.append("url_for_all_filings")
    values.append(f"https://www.sec.gov/edgar/browse/?CIK={cik}")
    keys.append("identifier")
    values.append(ticker_or_cik)


def _csv_filename(ticker_or_cik, form_type, cik, acc_num):
    return os.path.join(
        CSV_FILES_DIR, f"{ticker_or_cik}-{form_type}-{cik}-{acc_num}.csv".replace("/", "")
    )


def _write_csv(keys, values, ticker_or_cik, form_type, cik, acc_num):
    df = pd.DataFrame({"key": pd.Series(keys), "value": pd.Series(values)})
    df.to_csv(
        _csv_filename(ticker_or_cik, form_type, cik, acc_num),
        sep="\t",
        encoding="utf-8",
        index=False,
    )


def gen_csv(sec_doc_filename, ticker_or_cik, form_type, cik, acc_num):
    keys = []
    values = []

    _bookkeeping_info(keys, values, ticker_or_cik, cik, acc_num)
    resp_data = _fetch_response_from_api_curl(sec_doc_filename)
    if not resp_data:
        return
    for _key, _value in resp_data.items():
        keys.append(_key)
        values.append("\n".join([elem["text"] for elem in _value]))
    _write_csv(keys, values, ticker_or_cik, form_type, cik, acc_num)


def _gen_csv_no_api(filing_file_handle, ticker_or_cik, form_type, cik, acc_num):
    keys = []
    values = []
    filing_content = filing_file_handle.read()

    _bookkeeping_info(keys, values, ticker_or_cik, cik, acc_num)

    sec_document = SECDocument.from_string(filing_content)
    if "K" in form_type:
        sections = SECTIONS_10K
    elif "Q" in form_type:
        sections = SECTIONS_10Q
    else:
        sections = SECTIONS_S1

    for section in sections:
        print(section)
        result = "\n".join([str(elem) for elem in sec_document.get_section_narrative(section)])
        keys.append(section.name)
        values.append(result)
    _write_csv(keys, values, ticker_or_cik, form_type, cik, acc_num)


def gen_csvs(manifest_json_obj):
    """create CSVs given a manifest_json_obj which looks like:
      {
    "mmm": {
      "cik": "66740",
      "forms": {
        "10-Q": "000006674022000065"
      }
    },
    "0001156784": {
      "forms": {
        "S-1/A": "000149315222026129"
      },
      "cik": "0001156784"
    },
    """
    Path(CSV_FILES_DIR).mkdir(exist_ok=True)

    for ticker_or_cik in manifest_json_obj:
        cik = manifest_json_obj[ticker_or_cik]["cik"]
        for form_type in manifest_json_obj[ticker_or_cik]["forms"]:
            acc_num = manifest_json_obj[ticker_or_cik]["forms"][form_type]
            no_dir_filename = f"{ticker_or_cik}-{form_type}-{cik}-{acc_num}.xbrl".replace("/", "")
            sec_doc_filename = os.path.join(SEC_DOCS_DIR, no_dir_filename)
            csv_filename = _csv_filename(ticker_or_cik, form_type, cik, acc_num)
            if os.path.exists(csv_filename) and os.path.getsize(csv_filename) > 0:
                print(f"skipping api call for existing csv: {sec_doc_filename}", flush=True)
                continue
            print(f"{ticker_or_cik}", flush=True)
            gen_csv(sec_doc_filename, ticker_or_cik, form_type, cik, acc_num)


if __name__ == "__main__":
    if SEC_DOCS_DIR is None or CSV_FILES_DIR is None:
        raise RuntimeError("Environment vaiables SEC_DOCS_DIR and CSV_FILES_DIR must be set.")
    gen_csvs(parse_manifest_json())
