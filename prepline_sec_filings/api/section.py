#####################################################################
# THIS FILE IS AUTOMATICALLY GENERATED BY UNSTRUCTURED API TOOLS.
# DO NOT MODIFY DIRECTLY
#####################################################################

import os
import inspect
from typing import List

from fastapi import status, FastAPI, File, Form, Request, UploadFile
from slowapi.errors import RateLimitExceeded
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

RATE_LIMIT = os.environ.get("PIPELINE_API_RATE_LIMIT", "1/second")

from prepline_sec_filings.sections import (
    section_string_to_enum,
    validate_section_names,
    SECSection,
)
from prepline_sec_filings.sec_document import (
    SECDocument,
    REPORT_TYPES,
    VALID_FILING_TYPES,
)


from enum import Enum
import re

from unstructured.staging.base import convert_to_isd
from prepline_sec_filings.sections import (
    ALL_SECTIONS,
    SECTIONS_10K,
    SECTIONS_10Q,
    SECTIONS_S1,
)


def get_regex_enum(section_regex):
    class CustomSECSection(Enum):
        # NOTE(robinson) - The encode/decode step treats the requested
        # pattern as a raw string, such as r"risk factors"
        raw_regex = section_regex.encode("unicode_escape").decode()
        CUSTOM = re.compile(raw_regex)

        @property
        def pattern(self):
            return self.value

    return CustomSECSection.CUSTOM


def pipeline_api(text, m_section=[], m_section_regex=[]):
    """Many supported sections including: RISK_FACTORS, MANAGEMENT_DISCUSSION, and many more"""
    validate_section_names(m_section)

    sec_document = SECDocument.from_string(text)
    if sec_document.filing_type not in VALID_FILING_TYPES:
        raise ValueError(
            f"SEC document filing type {sec_document.filing_type} is not supported, "
            f"must be one of {','.join(VALID_FILING_TYPES)}"
        )
    results = {}
    if m_section == [ALL_SECTIONS]:
        filing_type = sec_document.filing_type
        if filing_type in REPORT_TYPES:
            if filing_type.startswith("10-K"):
                m_section = [enum.name for enum in SECTIONS_10K]
            elif filing_type.startswith("10-Q"):
                m_section = [enum.name for enum in SECTIONS_10Q]
            else:
                raise ValueError(f"Invalid report type: {filing_type}")

        else:
            m_section = [enum.name for enum in SECTIONS_S1]
    for section in m_section:
        results[section] = sec_document.get_section_narrative(
            section_string_to_enum[section]
        )
    for i, section_regex in enumerate(m_section_regex):
        regex_enum = get_regex_enum(section_regex)
        section_elements = sec_document.get_section_narrative(regex_enum)
        results[f"REGEX_{i}"] = section_elements
    return {
        section: convert_to_isd(section_narrative)
        for section, section_narrative in results.items()
    }


@app.post("/sec-filings/v0.0.1/section")
@limiter.limit(RATE_LIMIT)
async def pipeline_1(
    request: Request,
    file: UploadFile = File(),
    section: List[str] = Form(default=[]),
    section_regex: List[str] = Form(default=[]),
):

    text = file.file.read().decode("utf-8")
    response = pipeline_api(
        text,
        section,
        section_regex,
    )

    return response


@app.get("/healthcheck", status_code=status.HTTP_200_OK)
@limiter.limit(RATE_LIMIT)
async def healthcheck(request: Request):
    return {"healthcheck": "HEALTHCHECK STATUS: EVERYTHING OK!"}
