import json
import os

# File used to generate 'first' and 'last' for sample-first-last.json
# from the downloaded forms (through "make dl-test-artifacts")

# NOTE: This file is ran from the root path of the repository

from prepline_sec_filings.sec_document import SECDocument

from prepline_sec_filings.sections import section_string_to_enum

DIRECTORY = os.getcwd()

RISK_FACTOR_XFAILS = ["aig", "bgs"]

with open(
    os.path.join(DIRECTORY, "test_real_docs", "fixtures", "sample-first-last.json"),
    "r",
) as f:
    sample_first_last = json.load(f)

with open(os.path.join("test_real_docs", "test_utils", "examples.json")) as f:
    examples = json.load(f)


def get_file_from_ticker(ticker):
    cik = examples[ticker]["cik"]
    formtype = next(iter(examples[ticker]["forms"]))
    accession_number = examples[ticker]["forms"][formtype]
    with open(
        os.path.join(
            "test_real_docs",
            "sample-sec-docs",
            f"{ticker}-{formtype}-{cik}-{accession_number}.xbrl",
        )
    ) as f:
        out = f.read()
    return out


tickers_10q = [
    ticker for ticker in sample_first_last if "10-Q" in examples[ticker]["forms"]
]  # filter only 10-Q docs


def get_doc_elements(tickers):
    docs_all = {}
    for ticker in tickers:
        print("at ticker", ticker)
        text = get_file_from_ticker(ticker)
        doc = SECDocument.from_string(text).doc_after_cleaners(skip_headers_and_footers=True)
        docs_all[ticker] = {}
        docs_all[ticker]["doc"] = doc
        docs_all[ticker]["elements"] = doc.elements
    return docs_all


def get_doc(docs_all, ticker):
    return docs_all[ticker]["doc"], docs_all[ticker]["elements"]


sections = [
    "FINANCIAL_STATEMENTS",  # ITEM 1
    "MANAGEMENT_DISCUSSION",  # ITEM 2
    "MARKET_RISK_DISCLOSURES",  # ITEM 3
    "CONTROLS_AND_PROCEDURES",
]  # ITEM 4


def print_ticker(docs_all, ticker, sections=sections):
    doc, _ = get_doc(docs_all, ticker)
    print("### ", ticker, " ###")
    for section in sections:
        print("----", section, "-----")
        # skip if nothing is extracted
        if len(doc.get_section_narrative(section_string_to_enum[section])) == 0:
            continue
        print(doc.get_section_narrative(section_string_to_enum[section])[0])  # first
        print(doc.get_section_narrative(section_string_to_enum[section])[-1])  # last
        # for el in doc.get_section_narrative(section_string_to_enum[section]):
        #     print('+',clean_sec_text(el.text))


docs_all = get_doc_elements(tickers_10q)

for ticker in tickers_10q:
    print_ticker(docs_all, ticker)
