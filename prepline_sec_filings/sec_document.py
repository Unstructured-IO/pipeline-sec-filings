from functools import partial
import re
from typing import List, Optional, Iterable, Iterator, Any, Tuple
import sys

if sys.version_info < (3, 8):
    from typing_extensions import Final
else:
    from typing import Final

import numpy as np
import numpy.typing as npt
from sklearn.cluster import DBSCAN
from collections import defaultdict

from unstructured.cleaners.core import clean
from unstructured.documents.elements import Text, ListItem, NarrativeText, Title, Element
from unstructured.documents.html import HTMLDocument
from unstructured.nlp.partition import is_possible_title
from prepline_sec_filings.sections import SECSection

VALID_FILING_TYPES: Final[List[str]] = [
    "10-K",
    "10-Q",
    "S-1",
    "10-K/A",
    "10-Q/A",
    "S-1/A",
]
REPORT_TYPES: Final[List[str]] = ["10-K", "10-Q", "10-K/A", "10-Q/A"]
S1_TYPES: Final[List[str]] = ["S-1", "S-1/A"]

ITEM_TITLE_RE = re.compile(r"(?i)item \d{1,3}(?:[a-z]|\([a-z]\))?(?:\.)?(?::)?")

# NOTE(yuming): clean_sec_text is a partial cleaner from clean,
# and is used for cleaning a section of text from a SEC filing.
clean_sec_text = partial(clean, extra_whitespace=True, dashes=True, trailing_punctuation=True)

# Note(Nathan): These strings are titles from brks 10-Q, nks 10-K, bj S-1 forms,
#   which is_possible_title returned false due to
#   i) their word length being longer than title_max_word_length
#   ii) small sentence_min_length value, and
#   iii) low non_alpha_threshold,
#   so we want to relax this constraint when evaluating these strings only.
title_constraints_relaxed = [
    "Consolidated Balance Sheets as of March 31, 2021 (unaudited) and September 30, 2020",
    "Consolidated Statements of Operations for the three and six months \
        ended March 31, 2021 and 2020 (unaudited)",
    "Consolidated Statements of Comprehensive Income for the three and six months \
        ended March 31, 2021 and 2020 (unaudited)",
    "Consolidated Statements of Cash Flows for the six months \
        ended March 31, 2021 and 2020 (unaudited)",
    "Consolidated Statements of Changes in Stockholders Equity for the three and six months \
        ended March 31, 2021 and 2020 (unaudited)",
    "Notes to Consolidated Financial Statements (unaudited)",
    "Item 2. Management’s Discussion and Analysis of Financial Condition and Results of Operations",
    "Market for Registrant's Common Equity, Related Stockholder Matters \
        and Issuer Purchases of Equity Securities",
    "F-1",
]


def _raise_for_invalid_filing_type(filing_type: Optional[str]):
    if not filing_type:
        raise ValueError("Filing type is empty.")
    elif filing_type not in VALID_FILING_TYPES:
        raise ValueError(f"Filing type was {filing_type}. Expected: {VALID_FILING_TYPES}")


class SECDocument(HTMLDocument):
    filing_type = None

    def _filter_table_of_contents(self, elements: List[Text]) -> List[Text]:
        """Filter out unnecessary elements in the table of contents using keyword search."""
        elements = [
            el
            for el in elements
            if isinstance(el, (Title, NarrativeText))
            or (isinstance(el, Text) and not el.text.isnumeric())
        ]
        if self.filing_type in REPORT_TYPES:
            # NOTE(yuming): Narrow TOC as all elements within
            # the first two titles that contain the keyword 'part i\b'.
            start, end = None, None
            for i, element in enumerate(elements):
                if bool(re.match(r"(?i)part i\b", clean_sec_text(element.text))):
                    if start is None:
                        # NOTE(yuming): Found the start of the TOC section.
                        start = i
                    else:
                        # NOTE(yuming): Found the end of the TOC section.
                        end = i - 1
                        filtered_elements = elements[start:end]
                        return filtered_elements
            if start is not None:
                filtered_elements = elements[start:]
                # NOTE(Nathan): if the length of elements is too long,
                # it probably means that they are not part of toc.
                if len(filtered_elements) < 1000:
                    return filtered_elements
        elif self.filing_type in S1_TYPES:
            # NOTE(yuming): Narrow TOC as all elements within
            # the first pair of duplicated titles that contain the keyword 'prospectus'.
            title_indices = defaultdict(list)
            _start = None
            for i, element in enumerate(elements):
                clean_title_text = clean_sec_text(element.text).lower()
                title_indices[clean_title_text].append(i)
                if "prospectus" in clean_title_text:
                    _start = i
            duplicate_title_indices = {k: v for k, v in title_indices.items() if len(v) > 1}
            for title, indices in duplicate_title_indices.items():
                # NOTE(yuming): Make sure that we find the pair of duplicated titles.
                if "prospectus" in title and len(indices) == 2:
                    _start = indices[0]
                    _end = indices[1] - 1
                    filtered_elements = elements[_start:_end]
                    return filtered_elements
            if _start is not None:
                filtered_elements = elements[_start:]
                # NOTE(Nathan): if the length of elements is too long,
                # it probably means that they are not part of toc.
                if len(filtered_elements) < 1000:
                    return filtered_elements
        # NOTE(yuming): Probably better ways to improve TOC,
        # but now we return [] if it fails to find the keyword.
        return []

    def get_table_of_contents(self) -> HTMLDocument:
        """Identifies text sections that are likely the table of contents."""
        out_cls = self.__class__
        _raise_for_invalid_filing_type(self.filing_type)
        title_locs = to_sklearn_format(self.elements)
        if len(title_locs) == 0:
            return out_cls.from_elements([])
        # NOTE(alan): Might be a way to do the same thing that doesn't involve the transformations
        # necessary to get it into sklearn. We're just looking for densely packed Titles.
        res = DBSCAN(eps=6.0).fit_predict(title_locs)
        for i in range(res.max() + 1):
            idxs = cluster_num_to_indices(i, title_locs, res)
            cluster_elements: List[Text] = [self.elements[i] for i in idxs]
            if any(
                [
                    # TODO(alan): Maybe swap risk title out for something more generic? It helps to
                    # have 2 markers though, I think.
                    is_risk_title(el.text, self.filing_type)
                    for el in cluster_elements
                    if isinstance(el, Title)
                ]
            ) and any([is_toc_title(el.text) for el in cluster_elements if isinstance(el, Title)]):
                return out_cls.from_elements(self._filter_table_of_contents(cluster_elements))
        return out_cls.from_elements(self._filter_table_of_contents(self.elements))

    def get_section_narrative_no_toc(self, section: SECSection) -> List[NarrativeText]:
        """Identifies narrative text sections that fall under the given section heading without
        using the table of contents."""
        _raise_for_invalid_filing_type(self.filing_type)
        # NOTE(robinson) - We are not skipping table text because the risk narrative section
        # usually does not contain any tables and sometimes tables are used for
        # title formating
        section_elements: List[NarrativeText] = list()
        in_section = False
        for element in self.elements:
            is_title = is_possible_title(element.text)
            if in_section:
                if is_title and is_item_title(element.text, self.filing_type):
                    if section_elements:
                        return section_elements
                    else:
                        in_section = False
                elif isinstance(element, NarrativeText) or isinstance(element, ListItem):
                    section_elements.append(element)

            if is_title and is_section_elem(section, element, self.filing_type):
                in_section = True

        return section_elements

    def _get_toc_sections(self, section: SECSection, toc: HTMLDocument) -> Tuple[Text, Text]:
        """Identifies section title and next section title in TOC under the given section heading"""
        # Note(yuming): The matching section and the section after the matching section
        # can be thought of as placeholders to look for matching content below the toc.
        section_toc = first(
            el for el in toc.elements if is_section_elem(section, el, self.filing_type)
        )
        if section_toc is None:
            # NOTE(yuming): unable to identify the section in TOC
            return (None, None)

        after_section_toc = toc.after_element(section_toc)
        next_section_toc = first(
            el
            for el in after_section_toc.elements
            if not is_section_elem(section, el, self.filing_type)
        )
        if next_section_toc is None:
            # NOTE(yuming): unable to identify the next section title in TOC,
            # will leads to failure in finding the end of the section
            return (section_toc, None)
        return (section_toc, next_section_toc)

    def get_section_narrative(self, section: SECSection) -> List[NarrativeText]:
        """Identifies narrative text sections that fall under the given section heading"""
        _raise_for_invalid_filing_type(self.filing_type)
        # NOTE(robinson) - We are not skipping table text because the risk narrative section
        # usually does not contain any tables and sometimes tables are used for
        # title formating
        toc = self.get_table_of_contents()
        if not toc.pages:
            return self.get_section_narrative_no_toc(section)
        # Note(yuming): section_toc is the section title in TOC,
        # next_section_toc is the section title right after section_toc in TOC
        section_toc, next_section_toc = self._get_toc_sections(section, toc)
        if section_toc is None:
            # NOTE(yuming): fail to find the section title in TOC
            return []

        # NOTE(yuming): we use doc after next_section_toc instead of after toc
        # to workaround an issue where the TOC grabbed too many elements by
        # starting to parse after the section matched in the TOC
        doc_after_section_toc = self.after_element(
            next_section_toc if next_section_toc else section_toc
        )
        # NOTE(yuming): map section_toc to the section title after TOC
        # to find the start of the section
        section_start_element = get_element_by_title(
            reversed(doc_after_section_toc.elements), section_toc.text, self.filing_type
        )
        if section_start_element is None:
            return []
        doc_after_section_heading = self.after_element(section_start_element)

        # NOTE(yuming): Checks if section_toc is the last section in toc based on
        # the structure of the report filings or fails to find the section title in TOC.
        # returns everything up to the next Title element
        # to avoid the worst case of returning the entire doc.
        if self._is_last_section_in_report(section, toc) or next_section_toc is None:
            # returns everything after section_start_element in doc
            return get_narrative_texts(doc_after_section_heading, up_to_next_title=True)

        # NOTE(yuming): map next_section_toc to the section title after TOC
        # to find the start of the next section, which is also the end of the section we want
        section_end_element = get_element_by_title(
            doc_after_section_heading.elements, next_section_toc.text, self.filing_type
        )

        if section_end_element is None:
            # NOTE(yuming): returns everything up to the next Title element
            # to avoid the worst case of returning the entire doc.
            return get_narrative_texts(doc_after_section_heading, up_to_next_title=True)
        return get_narrative_texts(doc_after_section_heading.before_element(section_end_element))

    def get_risk_narrative(self) -> List[NarrativeText]:
        """Identifies narrative text sections that fall under the "risk" heading"""
        return self.get_section_narrative(SECSection.RISK_FACTORS)

    def doc_after_cleaners(
        self, skip_headers_and_footers=False, skip_table_text=False, inplace=False
    ) -> HTMLDocument:
        new_doc = super().doc_after_cleaners(skip_headers_and_footers, skip_table_text, inplace)
        if not inplace:
            # NOTE(alan): Copy filing_type since this attribute isn't in the base class
            new_doc.filing_type = self.filing_type
        return new_doc

    def _read_xml(self, content):
        super()._read_xml(content)
        # NOTE(alan): Get filing type from xml since this is not relevant to the base class.
        type_tag = self.document_tree.find(".//type")
        if type_tag is not None:
            self.filing_type = type_tag.text.strip()
        return self.document_tree

    def _is_last_section_in_report(self, section: SECSection, toc: HTMLDocument) -> bool:
        """Checks to see if the section is the last section in toc for a report types filing."""
        # Note(yuming): This method assume the section already exists in toc.
        if self.filing_type in ["10-K", "10-K/A"]:
            # try to get FORM_SUMMARY as last section, else then try to get EXHIBITS.
            if section == SECSection.FORM_SUMMARY:
                return True
            if section == SECSection.EXHIBITS:
                form_summary_section = first(
                    el
                    for el in toc.elements
                    if is_section_elem(SECSection.FORM_SUMMARY, el, self.filing_type)
                )
                # if FORM_SUMMARY is not in toc, the last section is EXHIBITS
                if form_summary_section is None:
                    return True
        if self.filing_type in ["10-Q", "10-Q/A"]:
            # try to get EXHIBITS as last section.
            if section == SECSection.EXHIBITS:
                return True
        return False


def get_narrative_texts(doc: HTMLDocument, up_to_next_title: Optional[bool] = False) -> List[Text]:
    """Returns a list of NarrativeText or ListItem from document,
    with option to return narrative texts only up to next Title element."""
    if up_to_next_title:
        narrative_texts = []
        for el in doc.elements:
            if isinstance(el, (NarrativeText, ListItem)):
                narrative_texts.append(el)
            else:
                break
        return narrative_texts
    else:
        return [el for el in doc.elements if isinstance(el, (NarrativeText, ListItem))]


def is_section_elem(section: SECSection, elem: Text, filing_type: Optional[str]) -> bool:
    """Checks to see if a text element matches the section title for a given filing type"""
    _raise_for_invalid_filing_type(filing_type)
    if section is SECSection.RISK_FACTORS:
        return is_risk_title(elem.text, filing_type=filing_type)
    else:

        def _is_matching_section_pattern(text):
            return bool(re.search(section.pattern, clean_sec_text(text, lowercase=True)))

        if filing_type in REPORT_TYPES:
            return _is_matching_section_pattern(remove_item_from_section_text(elem.text))
        else:
            return _is_matching_section_pattern(elem.text)


def is_item_title(title: str, filing_type: Optional[str]) -> bool:
    """Determines if a title corresponds to an item heading."""
    if filing_type in REPORT_TYPES:
        return is_10k_item_title(title)
    elif filing_type in S1_TYPES:
        return is_s1_section_title(title)
    return False


def is_risk_title(title: str, filing_type: Optional[str]) -> bool:
    """Checks to see if the title matches the pattern for the risk heading."""
    if filing_type in REPORT_TYPES:
        return is_10k_risk_title(clean_sec_text(title, lowercase=True))
    elif filing_type in S1_TYPES:
        return is_s1_risk_title(clean_sec_text(title, lowercase=True))
    return False


def is_toc_title(title: str) -> bool:
    """Checks to see if the title matches the pattern for the table of contents."""
    clean_title = clean_sec_text(title, lowercase=True)
    return (clean_title == "table of contents") or (clean_title == "index")


def is_10k_item_title(title: str) -> bool:
    """Determines if a title corresponds to a 10-K item heading."""
    return ITEM_TITLE_RE.match(clean_sec_text(title, lowercase=True)) is not None


def is_10k_risk_title(title: str) -> bool:
    """Checks to see if the title matches the pattern for the risk heading."""
    return ("1a" in title.lower() or "risk factors" in title.lower()) and not (
        "summary" in title.lower()
    )


def is_s1_section_title(title: str) -> bool:
    """Detemines if a title corresponds to a section title."""
    return title.strip().isupper()


def is_s1_risk_title(title: str) -> bool:
    """Checks to see if the title matches the pattern for the risk heading."""
    return title.strip().lower() == "risk factors"


def to_sklearn_format(elements: List[Element]) -> npt.NDArray[np.float32]:
    """The input to clustering needs to be locations in euclidean space, so we need to interpret
    the locations of Titles within the sequence of elements as locations in 1d space
    """
    is_title: npt.NDArray[np.bool_] = np.array(
        [is_possible_title(el.text) for el in elements][: len(elements)], dtype=bool
    )

    # Note(Nathan): relaxing title_max_word_length to 20 and sentence_min_length to 10
    #   when evaluating is_possible_title for strings in title_max_word_length_relaxed
    title_constraints_relaxed_idxs = [
        i for (i, el) in enumerate(elements) if el.text in title_constraints_relaxed
    ]
    title_constraints_relaxed_values = [
        is_possible_title(
            elements[i].text,
            title_max_word_length=20,
            sentence_min_length=10,
            non_alpha_threshold=0.1,
            language="",
        )
        for i in title_constraints_relaxed_idxs
    ]
    is_title[title_constraints_relaxed_idxs] = title_constraints_relaxed_values

    title_locs = np.arange(len(is_title)).astype(np.float32)[is_title].reshape(-1, 1)
    return title_locs


def cluster_num_to_indices(
    num: int, elem_idxs: npt.NDArray[np.float32], res: npt.NDArray[np.int_]
) -> List[int]:
    """Keeping in mind the input to clustering was indices in a list of elements interpreted as
    location in 1-d space, this function gives back the original indices of elements that are
    members of the cluster with the given number.
    """
    idxs = elem_idxs[res == num].astype(int).flatten().tolist()
    return idxs


def first(it: Iterable) -> Any:
    """Grabs the first item in an iterator."""
    try:
        out = next(iter(it))
    except StopIteration:
        out = None
    return out


def match_s1_toc_title_to_section(text: str, title: str) -> bool:
    """Matches an S-1 style title from the table of contents to the associated title in the document
    body"""
    return text == title


def match_10k_toc_title_to_section(text: str, title: str) -> bool:
    """Matches a 10-K style title from the table of contents to the associated title in the document
    body"""
    if re.match(ITEM_TITLE_RE, title):
        return text.startswith(title)
    else:
        text = remove_item_from_section_text(text)
        return text.startswith(title)


def remove_item_from_section_text(text: str) -> str:
    """Removes 'item' heading from section text for 10-K/Q forms as preparation for other matching
    techniques"""
    return re.sub(ITEM_TITLE_RE, "", text).strip()


def get_element_by_title(
    elements: Iterator[Element],
    title: str,
    filing_type: Optional[str],
) -> Optional[Element]:
    """Get element from Element list whose text approximately matches title"""
    _raise_for_invalid_filing_type(filing_type)
    if filing_type in REPORT_TYPES:
        match = match_10k_toc_title_to_section
    elif filing_type in S1_TYPES:
        match = match_s1_toc_title_to_section
    return first(
        el
        for el in elements
        if match(
            clean_sec_text(el.text, lowercase=True),
            clean_sec_text(title, lowercase=True),
        )
    )
