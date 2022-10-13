import json
import os
from pathlib import Path

import pytest

from prepline_sec_filings.sec_document import SECDocument, clean_sec_text
from unstructured.documents.html import HTMLListItem

from prepline_sec_filings.sections import SECSection, section_string_to_enum

DIRECTORY = Path(__file__).absolute().parent

RISK_FACTOR_XFAILS = ["aig", "bgs"]


with open(os.path.join("test_utils", "examples.json")) as f:
    examples = json.load(f)


with open(
    os.path.join(DIRECTORY, "fixtures", "sample-first-last.json"),
    "r",
) as f:
    sample_first_last = json.load(f)


@pytest.fixture(scope="module")
def docs_all():
    return {}


@pytest.fixture
def doc_elements(ticker, docs_all):
    if ticker not in docs_all:
        text = get_file_from_ticker(ticker)
        doc = SECDocument.from_string(text).doc_after_cleaners(skip_headers_and_footers=True)
        docs_all[ticker] = {}
        docs_all[ticker]["doc"] = doc
        docs_all[ticker]["elements"] = doc.elements
    return (docs_all[ticker]["doc"], docs_all[ticker]["elements"])


@pytest.fixture
def xfail(ticker, section, first_or_last):
    if ticker in RISK_FACTOR_XFAILS:
        return True
    elif ticker == "cl" and section in [
        SECSection.MANAGEMENT_DISCUSSION,
        SECSection.MARKET_RISK_DISCLOSURES,
    ]:
        return True
    elif ticker == "bc" and section == SECSection.USE_OF_PROCEEDS:
        return True
    elif ticker == "doc" and section == SECSection.OTHER_INFORMATION:
        return True
    elif (
        ticker == "cvs" and section == SECSection.PRINCIPAL_STOCKHOLDERS and first_or_last == "last"
    ):
        return True
    # TODO(yuming): The issue of this xfail is the same as the one in core-241
    elif ticker == "ehc" and section == SECSection.BUSINESS:
        return True
    return False


@pytest.fixture
def risk_samples():
    with open(os.path.join(os.path.dirname(__file__), "fixtures", "risk-samples.json"), "r") as f:
        out = json.load(f)
    return out


def get_file_from_ticker(ticker):
    cik = examples[ticker]["cik"]
    formtype = next(iter(examples[ticker]["forms"]))
    accession_number = examples[ticker]["forms"][formtype]
    with open(
        os.path.join("sample-sec-docs", f"{ticker}-{formtype}-{cik}-{accession_number}.xbrl")
    ) as f:
        out = f.read()
    return out


@pytest.mark.parametrize("ticker", [ticker for ticker in examples])
def test_samples_found(ticker, risk_samples, doc_elements):
    samples = risk_samples[ticker]
    if ticker in (
        "mmm",
        "aig",
        "rgld",
        "cri",
        "pepg",
        "ehc",
        "bj",
        "smtc",
        "bgs",
        "blco",
    ):
        pytest.xfail(reason="Need to re-examine test failure reasons")

    doc, _ = doc_elements
    parsed_risk_narratives = doc.get_risk_narrative()
    # The expected samples will be empty only when there is no risk factors section, so
    # the parsed narratives and samples to find should either both be empty or both be
    # populated.
    assert bool(parsed_risk_narratives) == bool(samples)
    for sample in samples:
        assert any(
            (
                # TODO(alan): Do cleaning directly in risk-samples.json and define cleaning
                # specifically for this test.
                clean_sec_text(sample) in clean_sec_text(risk_narrative.text)
                for risk_narrative in parsed_risk_narratives
            )
        )


@pytest.mark.parametrize(
    "ticker, section, first_or_last",
    [
        (ticker, section_string_to_enum[section], first_or_last)
        for ticker in sample_first_last
        for section in sample_first_last[ticker]
        for first_or_last in sample_first_last[ticker][section]
    ],
)
def test_first_last(ticker, doc_elements, section, first_or_last, xfail):
    if xfail:
        pytest.xfail()
    doc, _ = doc_elements
    parsed_risk_narratives = doc.get_section_narrative(section)
    sample = sample_first_last[ticker][section.name][first_or_last]
    idx = 0 if first_or_last == "first" else -1
    assert clean_sec_text(parsed_risk_narratives[idx].text) == clean_sec_text(sample)


def list_item_test_values():
    list_item_count_file = os.path.join(DIRECTORY, "fixtures", "list-item-counts.json")
    with open(list_item_count_file, "r") as f:
        list_item_counts = json.load(f)

    list_item_content_file = os.path.join(DIRECTORY, "fixtures", "list-item-content.json")
    with open(list_item_content_file, "r") as f:
        list_item_content = json.load(f)

    list_item_tests = list()
    for ticker, count in list_item_counts.items():
        content = list_item_content.get(ticker, None)
        list_item_tests.append((ticker, count, content))

    return list_item_tests


def check_first_list_item_section(section, expected_count, expected_content):
    count = 0
    in_list_item_section = False
    for i, element in enumerate(section):
        if not in_list_item_section and isinstance(element, HTMLListItem):
            in_list_item_section = True
            if expected_content:
                section_text = clean_sec_text(section[i].text)
                expected_text = clean_sec_text(expected_content[count])
                assert section_text == expected_text
            count += 1
        elif in_list_item_section and isinstance(element, HTMLListItem):
            if expected_content:
                section_text = clean_sec_text(section[i].text)
                expected_text = clean_sec_text(expected_content[count])
                assert section_text == expected_text
            count += 1
        elif in_list_item_section and not isinstance(element, HTMLListItem):
            return count

    assert count == expected_count

    return count


@pytest.mark.parametrize("ticker, expected_count, expected_content", list_item_test_values())
def test_list_items(ticker, expected_count, expected_content):
    if ticker in RISK_FACTOR_XFAILS:
        pytest.xfail(reason="xfail for risk factor section. therefore can't count list items")
    text = get_file_from_ticker(ticker)
    doc = SECDocument.from_string(text)
    risk_section = doc.get_section_narrative(SECSection.RISK_FACTORS)
    check_first_list_item_section(risk_section, expected_count, expected_content)
