from itertools import product
import pytest

from unstructured.documents.base import NarrativeText
from unstructured.documents.elements import Title

from prepline_sec_filings.sec_document import (
    SECDocument,
    first,
    get_element_by_title,
    is_item_title,
    is_risk_title,
    _raise_for_invalid_filing_type,
    is_toc_title,
    match_s1_toc_title_to_section,
    match_10k_toc_title_to_section,
    remove_item_from_section_text,
    get_narrative_texts,
)
from prepline_sec_filings.sections import SECSection


@pytest.fixture
def table_toc(form_type):
    is_s1 = form_type == "S-1"
    return f"""<table>
    <tr><td><p>TABLE OF CONTENTS</p></td><td></td></tr>
    <tr><td></td><td></td></tr>
    <p>{'Part I. OTHER INFORMATION' if not is_s1 else 'None'}</p>
    <p>{'ITEM 1. ' if not is_s1 else ''}PROSPECTUS SUMMARY</p>
    <tr><td><p>{'ITEM 1A. ' if not is_s1 else ''}RISK FACTORS</p></td><td>1</td></tr>
    <tr><td><p>{'ITEM 1B. ' if not is_s1 else ''}UNRESOLVED STAFF COMMENTS</p></td><td>1</td></tr>
    <tr><td><p>{'ITEM 2 ' if not is_s1 else ''}DIVIDEND POLICY</p></td><td>1</td></tr>
    <tr><td><p>{'ITEM 3 ' if not is_s1 else ''}CAPITALIZATION</p></td><td>1</td></tr>
    <tr><td><p>{'ITEM 4 ' if not is_s1 else ''}DILUTION</p></td><td>1</td></tr>
    <tr><td><p>{'ITEM 5 ' if not is_s1 else ''}WOLVERINES AND BEARS</p></td><td>1</td></tr>
    <tr><td><p>{'ITEM 6 ' if not is_s1 else ''}PROPERTIES</p></td><td>1</td></tr>
    </table>"""


@pytest.fixture
def sample_document(form_type, table_toc, use_toc):
    is_s1 = form_type == "S-1"
    return f"""<SEC-DOCUMENT>
    <TYPE>{form_type}
    <COMPANY>Proctor & Gamble
    <HTML>
        {table_toc if use_toc else ''}
        <p>SECURITY AND EXCHANGE COMISSION FILING</p>
        <p>{'Part I.' if not is_s1 else 'None'}</p>
        <p>{'OTHER INFORMATION' if not is_s1 else 'None'}</p>
        <p>{'ITEM 1. ' if not is_s1 else ''}PROSPECTUS SUMMARY</p>
        <p>This is a section on prospectus.</p>
        <p>{'ITEM 1A. ' if not is_s1 else ''}RISK FACTORS</p>
        <p>Wolverines</p>
        <p>The business could be attacked by wolverines.</p>
        <p>Bears</p>
        <p>The business could be attacked by bears.</p>
        <p>{'ITEM 1B. ' if not is_s1 else ''}UNRESOLVED STAFF COMMENTS</p>
        <p>None</p>
        <p>{'ITEM 2 ' if not is_s1 else ''}DIVIDEND POLICY</p>
        <p>Dispersing Dividends</p>
        <p>Sometimes we disperse dividends, and everyone gets money.</p>
        <p>Uh Oh</p>
        <p>Sometimes we don't disperse dividends, and nobody gets money.</p>
        <p>{'ITEM 3 ' if not is_s1 else ''}CAPITALIZATION</p>
        <p>None</p>
        <p>{'ITEM 4 ' if not is_s1 else ''}DILUTION</p>
        <p>None</p>
        <p>{'ITEM 5 ' if not is_s1 else ''}WOLVERINES AND BEARS</p>
        <p>Just to reiterate, our business could be the victim of a wolverine attack.</p>
        <p>Also bears attack us literally twice a week.</p>
        <p>{'ITEM 6 ' if not is_s1 else ''}PROPERTIES</p>
        <p>One building in the middle of the woods.</p>
        <p>Why did we build it here?</p>
        <p>We really should not have done this.</p>
        <p>It was Steve's idea.</p>
    </HTML>
</SEC-DOCUMENT>"""


@pytest.fixture
def sample_document_with_last_sections(form_type, has_form_summary_section, has_exhibits_section):
    is_s1 = form_type == "S-1"
    show_exhibit = (not is_s1) and has_exhibits_section
    show_form_summary = (not is_s1) and has_form_summary_section

    table_toc = f"""<table>
    <tr><td><p>TABLE OF CONTENTS</p></td><td></td></tr>
    <tr><td></td><td></td></tr>
    <p>{'Part I. OTHER INFORMATION' if not is_s1 else 'None'}</p>
    <p>{'ITEM 1. ' if not is_s1 else ''}PROSPECTUS SUMMARY</p>
    {'<tr><td><p>ITEM 7 EXHIBIT</p></td><td>1</td></tr>' if show_exhibit else ''}
    {'<tr><td><p>ITEM 8 FORM 10-K SUMMARY</p></td><td>1</td></tr>' if show_form_summary else ''}
    </table>"""

    return f"""<SEC-DOCUMENT>
    <TYPE>{form_type}
    <COMPANY>Proctor & Gamble
    <HTML>
        {table_toc}
        <p>SECURITY AND EXCHANGE COMISSION FILING</p>
        <p>{'Part I.' if not is_s1 else 'None'}</p>
        <p>{'OTHER INFORMATION' if not is_s1 else 'None'}</p>
        <p>{'ITEM 1. ' if not is_s1 else ''}PROSPECTUS SUMMARY</p>
        <p>This is a section on prospectus.</p>
        {'<p>ITEM 7 EXHIBIT</p>' if show_exhibit else ''}
        {'<p>This is a section on exhibit.</p>' if show_exhibit else ''}
        {'<p>ITEM 8 FORM 10-K SUMMARY</p>' if show_form_summary else ''}
        {'<p>This is a section on form summary.</p>' if show_form_summary else ''}
    </HTML>
</SEC-DOCUMENT>"""


class MockElement:
    def __init__(self, text):
        self.text = text


@pytest.fixture
def elements():
    texts = ["Risk Factors:", "ITEM 1a. risk factors", "ITEM 3. Cats", "Summary"]
    return [MockElement(text) for text in texts]


@pytest.mark.parametrize(
    "section_name, form_type, use_toc",
    product(
        [SECSection.DIVIDEND_POLICY],
        ["10-Q", "10-K", "S-1"],
        [True, False],
    ),
)
def test_get_dividend_narrative(section_name, sample_document):
    sec_document = SECDocument.from_string(sample_document)
    sections = sec_document.get_section_narrative(section_name)
    assert sections == [
        NarrativeText(text="Sometimes we disperse dividends, and everyone gets money."),
        NarrativeText(text="Sometimes we don't disperse dividends, and nobody gets money."),
    ]


@pytest.mark.parametrize("form_type, use_toc", product(("10-Q", "10-K", "S-1"), (True, False)))
def test_get_risk_narrative(sample_document):
    sec_document = SECDocument.from_string(sample_document)
    risk_sections = sec_document.get_risk_narrative()
    assert risk_sections == [
        NarrativeText(text="The business could be attacked by wolverines."),
        NarrativeText(text="The business could be attacked by bears."),
    ]


@pytest.mark.parametrize("form_type, use_toc", product(("10-Q", "10-K", "S-1"), (True, False)))
def test_get_table_of_contents(sample_document, form_type, use_toc):
    is_s1 = form_type == "S-1"
    sec_document = SECDocument.from_string(sample_document)
    toc_elements = sec_document.get_table_of_contents().elements
    if use_toc:
        assert Title(text=f"{'ITEM 1A. ' if not is_s1 else ''}RISK FACTORS") in toc_elements
    else:
        assert toc_elements == []


def test_get_10k_table_of_contents_processes_empty_doc():
    sec_document = SECDocument.from_string("<SEC-DOCUMENT><TYPE>10-K</SEC-DOCUMENT>")
    risk_sections = sec_document.get_table_of_contents().elements
    assert risk_sections == list()


def test_get_risk_narrative_raises_with_wrong_type():
    sec_document = SECDocument.from_string("<SEC-DOCUMENT><TYPE>999-ZZZ</SEC-DOCUMENT>")
    with pytest.raises(ValueError):
        sec_document.get_risk_narrative()


@pytest.mark.parametrize("form_type, use_toc", product(["10-K", "10-Q", "S-1"], [True]))
def test__get_toc_sections(sample_document, form_type):
    is_s1 = form_type == "S-1"
    sec_document = SECDocument.from_string(sample_document)
    toc = sec_document.get_table_of_contents()
    # finds the section titles
    section_toc, next_section_toc = sec_document._get_toc_sections(
        SECSection.PROSPECTUS_SUMMARY, toc
    )
    assert (
        section_toc.text == f"{'ITEM 1. ' if not is_s1 else ''}PROSPECTUS SUMMARY"
        and next_section_toc.text == f"{'ITEM 1A. ' if not is_s1 else ''}RISK FACTORS"
    )
    # fails to find the section_toc because it's not in the document
    section_toc, next_section_toc = sec_document._get_toc_sections(SECSection.EXHIBITS, toc)
    assert (section_toc, next_section_toc) == (None, None)
    assert sec_document.get_section_narrative(SECSection.EXHIBITS) == []


@pytest.mark.parametrize(
    "form_type, has_form_summary_section, has_exhibits_section, expected_last_section",
    [
        ("10-K", True, False, SECSection.FORM_SUMMARY),
        ("10-K", False, True, SECSection.EXHIBITS),
        ("10-K", True, True, SECSection.FORM_SUMMARY),
        ("10-Q", False, True, SECSection.EXHIBITS),
    ],
)
def test__is_last_section_in_report(sample_document_with_last_sections, expected_last_section):
    sec_document = SECDocument.from_string(sample_document_with_last_sections)
    toc = sec_document.get_table_of_contents()
    assert sec_document._is_last_section_in_report(expected_last_section, toc)
    assert len(sec_document.get_section_narrative(expected_last_section)) == 1


@pytest.mark.parametrize(
    "section", [SECSection.RISK_FACTORS, SECSection.CAPITALIZATION, SECSection.DIVIDEND_POLICY]
)
def test_get_10k_section_narrative_processes_empty_doc(section):
    sec_document = SECDocument.from_string("<SEC-DOCUMENT><TYPE>10-K</SEC-DOCUMENT>")
    sections = sec_document.get_section_narrative(section)
    assert sections == list()


@pytest.mark.parametrize("form_type, use_toc", product(["10-K", "10-Q", "S-1"], [False]))
def test_get_filing_type(sample_document, form_type):
    sec_document = SECDocument.from_string(sample_document)
    assert sec_document.filing_type == form_type


def test_get_filing_type_is_none_when_missing():
    sec_document = SECDocument.from_string("<SEC-DOCUMENT></SEC-DOCUMENT>")
    assert sec_document.filing_type is None


def test_get_narrative_texts_up_to_next_title():
    document_starts_with_narrative_text = """
    <SEC-DOCUMENT>
    <TYPE> 10-K
    <COMPANY>Proctor & Gamble
    <HTML>
        <p>this is a narrative text.</p>
        <p>'NEXT TITLE'</p>
    </HTML>
    </SEC-DOCUMENT>"""
    sec_document = SECDocument.from_string(document_starts_with_narrative_text)
    narrative_texts_up_to_next_title = get_narrative_texts(sec_document, up_to_next_title=True)
    assert narrative_texts_up_to_next_title == [NarrativeText(text="this is a narrative text.")]


@pytest.mark.parametrize(
    "title, expected",
    [
        ("ITEM 1A.", True),
        ("item 1a.", True),
        ("Item 1.", True),
        ("Item 3:", True),
        ("Item 3(a):", True),
        ("Item 3(a): ", True),
        (
            "ITEM 5(a).: MARKET FOR REGISTRANT’S COMMON EQUITY, RELATED STOCKHOLDER MATTERS AND "
            "ISSUER PURCHASES OF EQUITY SECURITIES",
            True,
        ),
        ("Item 12A.", True),
        ("This is a paragraph about an item", False),
        ("RISK FACTORS", False),
        ("Risk Factors", False),
    ],
)
def test_is_10k_item_title(title, expected):
    assert is_item_title(title, "10-K") == expected


@pytest.mark.parametrize(
    "title, expected",
    [
        ("ITEM 1A.", True),
        ("item 1a.", True),
        ("Item 1.", False),
        ("Item 12A.", False),
        ("This is a paragraph about an item", False),
        ("RISK FACTORS", True),
        ("Risk Factors", True),
        ("DISCLOSURES", False),
        ("Disclosures", False),
        ("SUMMARY OF RISK FACTORS", False),
    ],
)
def test_is_10_k_risk_title(title, expected):
    assert is_risk_title(title, "10-K") == expected


@pytest.mark.parametrize(
    "title, expected",
    [
        ("RISK FACTORS", True),
        ("SPECIAL NOTE", True),
        ("Risk Factors Summary", False),
    ],
)
def test_is_s1_item_title(title, expected):
    assert is_item_title(title, "S-1") == expected


@pytest.mark.parametrize(
    "title, expected",
    [
        ("RISK FACTORS", True),
        ("SPECIAL NOTE", False),
        ("Risk Factors Summary", False),
    ],
)
def test_is_s1_risk_title(title, expected):
    assert is_risk_title(title, "S-1") == expected


@pytest.mark.parametrize(
    "text, title, expected",
    [
        ("risk factors", "risk factors", True),
        ("risk factors", "something else", False),
        ("summary of risk factors", "risk factors", False),
    ],
)
def test_match_s1_toc_title_to_section(text, title, expected):
    assert match_s1_toc_title_to_section(text, title) == expected


@pytest.mark.parametrize(
    "text, title, expected",
    [
        ("risk factors", "risk factors", True),
        ("summary of risk factors", "risk factors", False),
        ("item 1a. risk factors", "item 1a", True),
        ("item 1a.", "item 1a", True),
        ("item 1a. risk factors", "risk factors", True),
        ("item 1a. summary of risk factors", "risk factors", False),
        ("item 1a. summary of risk factors", "something else", False),
    ],
)
def test_match_10k_toc_title_to_section(text, title, expected):
    assert match_10k_toc_title_to_section(text, title) == expected


@pytest.mark.parametrize(
    "text, expected",
    [("Item 1a.  Risk Factors", "Risk Factors"), ("Risk Factors", "Risk Factors")],
)
def test_remove_item_from_section_text(text, expected):
    assert remove_item_from_section_text(text) == expected


@pytest.mark.parametrize(
    "title, expected",
    [("Table of contents", True), ("Risk Factors", False), ("Index", True)],
)
def test_is_toc_title(title, expected):
    assert is_toc_title(title) == expected


def test_invalid_item_title_returns_false():
    assert is_item_title("TEST", "INVALID") is False


def test_invalid_risk_title_returns_false():
    assert is_risk_title("TEST", "INVALID") is False


def test_empty_filing_type_raises():
    with pytest.raises(ValueError):
        _raise_for_invalid_filing_type(None)


@pytest.mark.parametrize("it, expected", [(["a"], "a"), (["b", "a"], "b"), ([], None)])
def test_first(it, expected):
    result = first(it)
    if result is None:
        assert expected is None
    else:
        assert result == expected


@pytest.mark.parametrize(
    "title, filing_type, expected",
    [
        ("risk factors", "S-1", "Risk Factors:"),
        ("item 1a", "10-Q", "ITEM 1a. risk factors"),
        ("cats", "10-Q", "ITEM 3. Cats"),
        ("cats", "S-1", None),
        ("summary", "S-1", "Summary"),
        ("another title", "10-K", None),
    ],
)
def test_get_element_by_title(elements, title, filing_type, expected):
    result = get_element_by_title(elements, title, filing_type)
    if result is None:
        assert expected is None
    else:
        assert result.text == expected


@pytest.mark.parametrize("form_type, use_toc", [("10-Q", True)])
def test_doc_after_cleaners_keeps_filing_type(form_type, sample_document):
    sec_document = SECDocument.from_string(sample_document).doc_after_cleaners()
    assert sec_document.filing_type == form_type
