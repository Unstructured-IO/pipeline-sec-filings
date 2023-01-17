#####################################################################
# THIS FILE IS AUTOMATICALLY GENERATED BY UNSTRUCTURED API TOOLS.
# DO NOT MODIFY DIRECTLY
#####################################################################

import os
from typing import List, Union
from fastapi import status, FastAPI, File, Form, Request, UploadFile, APIRouter
from slowapi.errors import RateLimitExceeded
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from fastapi.responses import PlainTextResponse
import json
from fastapi.responses import StreamingResponse
from starlette.types import Send
from base64 import b64encode
from typing import Optional, Mapping, Iterator, Tuple
import secrets
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
import signal
from unstructured.staging.base import convert_to_isd
from prepline_sec_filings.sections import (
    ALL_SECTIONS,
    SECTIONS_10K,
    SECTIONS_10Q,
    SECTIONS_S1,
)
import io
import csv
from typing import Dict
from unstructured.documents.elements import Text, NarrativeText, Title, ListItem
from unstructured.staging.label_studio import stage_for_label_studio


limiter = Limiter(key_func=get_remote_address)
app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
router = APIRouter()

RATE_LIMIT = os.environ.get("PIPELINE_API_RATE_LIMIT", "1/second")


def is_expected_response_type(media_type, response_type):
    if media_type == "application/json" and response_type not in [dict, list]:
        return True
    elif media_type == "text/csv" and response_type != str:
        return True
    else:
        return False


# pipeline-api


class timeout:
    def __init__(self, seconds=1, error_message="Timeout"):
        self.seconds = seconds
        self.error_message = error_message

    def handle_timeout(self, signum, frame):
        raise TimeoutError(self.error_message)

    def __enter__(self):
        try:
            signal.signal(signal.SIGALRM, self.handle_timeout)
            signal.alarm(self.seconds)
        except ValueError:
            pass

    def __exit__(self, type, value, traceback):
        try:
            signal.alarm(0)
        except ValueError:
            pass


def get_regex_enum(section_regex):
    class CustomSECSection(Enum):
        CUSTOM = re.compile(section_regex)

        @property
        def pattern(self):
            return self.value

    return CustomSECSection.CUSTOM


def convert_to_isd_csv(results: dict) -> str:
    """
    Returns the representation of document elements as an Initial Structured Document (ISD)
    in CSV Format.
    """
    csv_fieldnames: List[str] = ["section", "element_type", "text"]
    new_rows = []
    for section, section_narrative in results.items():
        rows: List[Dict[str, str]] = convert_to_isd(section_narrative)
        for row in rows:
            new_row_item = dict()
            new_row_item["section"] = section
            new_row_item["element_type"] = row["type"]
            new_row_item["text"] = row["text"]
            new_rows.append(new_row_item)

    with io.StringIO() as buffer:
        csv_writer = csv.DictWriter(buffer, fieldnames=csv_fieldnames)
        csv_writer.writeheader()
        csv_writer.writerows(new_rows)
        return buffer.getvalue()


# List of valid response schemas
LABELSTUDIO = "labelstudio"
ISD = "isd"


def pipeline_api(
    text,
    response_type="application/json",
    m_section=[],
    m_section_regex=[],
    response_schema="isd",
):
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
        results[section] = sec_document.get_section_narrative(section_string_to_enum[section])
    for i, section_regex in enumerate(m_section_regex):
        regex_enum = get_regex_enum(section_regex)
        with timeout(seconds=5):
            section_elements = sec_document.get_section_narrative(regex_enum)
            results[f"REGEX_{i}"] = section_elements
    if response_type == "application/json":
        if response_schema == LABELSTUDIO:
            return {
                section: stage_for_label_studio(section_narrative)
                for section, section_narrative in results.items()
            }
        elif response_schema == ISD:
            return {
                section: convert_to_isd(section_narrative)
                for section, section_narrative in results.items()
            }
        else:
            raise ValueError(f"Unsupported response schema for {response_schema}")
    elif response_type == "text/csv":
        if response_schema != ISD:
            raise ValueError(f"Unsupported response schema for {response_schema}")
        return convert_to_isd_csv(results)
    else:
        raise ValueError(f"Unsupported response type for {response_type}")


class MultipartMixedResponse(StreamingResponse):
    CRLF = b"\r\n"

    def __init__(self, *args, content_type: str = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.content_type = content_type

    def init_headers(self, headers: Optional[Mapping[str, str]] = None) -> None:
        super().init_headers(headers)
        self.boundary_value = secrets.token_hex(16)
        content_type = f'multipart/mixed; boundary="{self.boundary_value}"'
        self.raw_headers.append((b"content-type", content_type.encode("latin-1")))

    @property
    def boundary(self):
        return b"--" + self.boundary_value.encode()

    def _build_part_headers(self, headers: dict) -> bytes:
        header_bytes = b""
        for header, value in headers.items():
            header_bytes += f"{header}: {value}".encode() + self.CRLF
        return header_bytes

    def build_part(self, chunk: bytes) -> bytes:
        part = self.boundary + self.CRLF
        part_headers = {
            "Content-Length": len(chunk),
            "Content-Transfer-Encoding": "base64",
        }
        if self.content_type is not None:
            part_headers["Content-Type"] = self.content_type
        part += self._build_part_headers(part_headers)
        part += self.CRLF + chunk + self.CRLF
        return part

    async def stream_response(self, send: Send) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": self.status_code,
                "headers": self.raw_headers,
            }
        )
        async for chunk in self.body_iterator:
            if not isinstance(chunk, bytes):
                chunk = chunk.encode(self.charset)
                chunk = b64encode(chunk)
            await send(
                {
                    "type": "http.response.body",
                    "body": self.build_part(chunk),
                    "more_body": True,
                }
            )

        await send({"type": "http.response.body", "body": b"", "more_body": False})


@router.post("/sec-filings/v0.2.0/section")
@limiter.limit(RATE_LIMIT)
async def pipeline_1(
    request: Request,
    text_files: Union[List[UploadFile], None] = File(default=None),
    output_format: Union[str, None] = Form(default=None),
    output_schema: str = Form(default=None),
    section: List[str] = Form(default=[]),
    section_regex: List[str] = Form(default=[]),
):
    content_type = request.headers.get("Accept")

    default_response_type = output_format or "application/json"
    if not content_type or content_type == "*/*" or content_type == "multipart/mixed":
        media_type = default_response_type
    else:
        media_type = content_type

    default_response_schema = output_schema or "isd"

    if isinstance(text_files, list) and len(text_files):
        if len(text_files) > 1:
            if content_type and content_type not in [
                "*/*",
                "multipart/mixed",
                "application/json",
            ]:
                return PlainTextResponse(
                    content=(
                        f"Conflict in media type {content_type}"
                        ' with response type "multipart/mixed".\n'
                    ),
                    status_code=status.HTTP_406_NOT_ACCEPTABLE,
                )

            def response_generator(is_multipart):
                for file in text_files:

                    text = file.file.read().decode("utf-8")

                    response = pipeline_api(
                        text,
                        m_section=section,
                        m_section_regex=section_regex,
                        response_type=media_type,
                        response_schema=default_response_schema,
                    )
                    if is_multipart:
                        if type(response) not in [str, bytes]:
                            response = json.dumps(response)
                    yield response

            if content_type == "multipart/mixed":
                return MultipartMixedResponse(
                    response_generator(is_multipart=True), content_type=media_type
                )
            else:
                return response_generator(is_multipart=False)
        else:

            text_file = text_files[0]
            text = text_file.file.read().decode("utf-8")

            response = pipeline_api(
                text,
                m_section=section,
                m_section_regex=section_regex,
                response_type=media_type,
                response_schema=default_response_schema,
            )
            
            if is_expected_response_type(media_type, type(response)):
                return PlainTextResponse(
                    content=(
                        f"Conflict in media type {media_type}"
                        f" with response type {type(response)}.\n"
                    ),
                    status_code=status.HTTP_406_NOT_ACCEPTABLE,
                )
            valid_response_types = ["application/json", "text/csv", "*/*"]
            if media_type in valid_response_types:
                valid_response_schemas = ["isd"]
                if media_type == "application/json":
                    valid_response_schemas.append("labelstudio")
                if response_schema not in valid_response_schemas:
                    return PlainTextResponse(
                        content=f"Unsupported response schema {response_schema}.\n",
                        status_code=status.HTTP_406_NOT_ACCEPTABLE,
                    )

                return response
            else:
                return PlainTextResponse(
                    content=f"Unsupported media type {media_type}.\n",
                    status_code=status.HTTP_406_NOT_ACCEPTABLE,
                )

    else:
        return PlainTextResponse(
            content='Request parameter "text_files" is required.\n',
            status_code=status.HTTP_400_BAD_REQUEST,
        )


@app.get("/healthcheck", status_code=status.HTTP_200_OK)
async def healthcheck(request: Request):
    return {"healthcheck": "HEALTHCHECK STATUS: EVERYTHING OK!"}


app.include_router(router)
