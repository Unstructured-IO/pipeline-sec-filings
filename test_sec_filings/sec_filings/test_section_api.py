import os
import pytest
import csv
from io import StringIO

from fastapi.testclient import TestClient

from unstructured_api_tools.pipelines.api_conventions import get_pipeline_path

from prepline_sec_filings.api.app import app as core_app
from prepline_sec_filings.api.section import app

SECTION_ROUTE = get_pipeline_path("section")


def generate_sample_document(form_type):
    is_s1 = form_type == "S-1"
    return f"""<SEC-DOCUMENT>
    <TYPE>{form_type}
    <COMPANY>Proctor & Gamble
    <HTML>
        <p>SECURITY AND EXCHANGE COMISSION FILING</p>
        <p>ITEM 1. BUSINESS</p>
        <p>This is a section and great and wonderful business dealings.</p>
        <p>{'ITEM 1A. ' if not is_s1 else ''}RISK FACTORS</p>
        <p>Wolverines</p>
        <p>The business could be attacked by wolverines.</p>
        <p>Bears</p>
        <p>The business could be attacked by bears.</p>
        <p>{'ITEM 1B. ' if not is_s1 else ''}UNRESOLVED STAFF COMMENTS</p>
        <p>None</p>
        <p>PROSPECTUS SUMMARY</p>
        <p>Here is a summary of the prospectus</p>
    </HTML>
</SEC-DOCUMENT>"""


@pytest.mark.parametrize(
    "form_type, section",
    [
        ("10-K", "RISK_FACTORS"),
        ("10-Q", "RISK_FACTORS"),
        ("S-1", "RISK_FACTORS"),
        ("10-K", "_ALL"),
        ("10-Q", "_ALL"),
        ("S-1", "_ALL"),
    ],
)
def test_section_narrative_api(form_type, section, tmpdir):
    sample_document = generate_sample_document(form_type)
    filename = os.path.join(tmpdir.dirname, "wilderness.xbrl")
    with open(filename, "w") as f:
        f.write(sample_document)

    # NOTE(robinson) - Reset the rate limit to avoid 429s in tests
    app.state.limiter.reset()
    client = TestClient(app)
    response = client.post(
        SECTION_ROUTE,
        files=[("text_files", (filename, open(filename, "rb"), "text/plain"))],
        data={"section": [section]},
    )

    assert response.status_code == 200
    response_dict = response.json()

    assert response_dict["RISK_FACTORS"] == [
        {
            "text": "The business could be attacked by wolverines.",
            "type": "NarrativeText",
        },
        {
            "text": "The business could be attacked by bears.",
            "type": "NarrativeText",
        },
    ]


@pytest.mark.parametrize(
    "form_type",
    [
        ("10-K"),
        ("10-Q"),
        ("S-1"),
    ],
)
def test_section_narrative_api_with_custom_regex(form_type, tmpdir):
    sample_document = generate_sample_document(form_type)
    filename = os.path.join(tmpdir.dirname, "wilderness.xbrl")
    with open(filename, "w") as f:
        f.write(sample_document)

    # NOTE(robinson) - Reset the rate limit to avoid 429s in tests
    app.state.limiter.reset()
    client = TestClient(app)
    response = client.post(
        SECTION_ROUTE,
        files=[("text_files", (filename, open(filename, "rb"), "text/plain"))],
        data={"section_regex": ["risk factors"]},
    )

    assert response.status_code == 200
    response_dict = response.json()

    assert response_dict["REGEX_0"] == [
        {
            "text": "The business could be attacked by wolverines.",
            "type": "NarrativeText",
        },
        {
            "text": "The business could be attacked by bears.",
            "type": "NarrativeText",
        },
    ]


@pytest.mark.parametrize(
    "form_type",
    [
        ("10-K"),
        ("10-Q"),
        ("S-1"),
    ],
)
def test_section_narrative_api_with_custom_regex_with_special_chars(form_type, tmpdir):
    sample_document = generate_sample_document(form_type)
    filename = os.path.join(tmpdir.dirname, "wilderness.xbrl")
    with open(filename, "w") as f:
        f.write(sample_document)

    # NOTE(robinson) - Reset the rate limit to avoid 429s in tests
    app.state.limiter.reset()
    client = TestClient(app)
    response = client.post(
        SECTION_ROUTE,
        files=[("text_files", (filename, open(filename, "rb"), "text/plain"))],
        data={"section_regex": ["^(?:prospectus )?summary$"]},
    )

    assert response.status_code == 200
    response_dict = response.json()

    assert response_dict["REGEX_0"] == [
        {
            "text": "Here is a summary of the prospectus",
            "type": "NarrativeText",
        },
    ]


@pytest.mark.parametrize(
    "form_types, section",
    [
        (["10-K", "10-Q"], "RISK_FACTORS"),
        (["10-K", "10-Q"], "_ALL"),
    ],
)
def test_section_narrative_api_with_multiple_uploads(form_types, section, tmpdir):
    filenames = []
    for idx, form_type in enumerate(form_types):
        sample_document = generate_sample_document(form_type)
        filename = os.path.join(tmpdir.dirname, f"wilderness_{idx}.xbrl")
        with open(filename, "w") as f:
            f.write(sample_document)
        filenames.append(filename)

    # NOTE(robinson) - Reset the rate limit to avoid 429s in tests
    app.state.limiter.reset()
    client = TestClient(app)
    files = [
        ("text_files", (filename, open(filename, "rb"), "text/plain")) for filename in filenames
    ]
    response = client.post(
        SECTION_ROUTE,
        files=files,
        headers={
            "Accept": "multipart/mixed",
        },
        data={"section": [section]},
    )

    assert response.status_code == 200

    if len(filenames) > 1:
        assert "multipart/mixed" in response.headers["content-type"]
    else:
        response_dict = response.json()

        assert response_dict["RISK_FACTORS"] == [
            {
                "text": "The business could be attacked by wolverines.",
                "type": "NarrativeText",
            },
            {
                "text": "The business could be attacked by bears.",
                "type": "NarrativeText",
            },
        ]


@pytest.mark.parametrize(
    "form_types, section, accept_header, response_status",
    [
        (["10-K", "10-Q"], "RISK_FACTORS", "multipart/mixed", 200),
        (["10-K", "10-Q"], "_ALL", "application/json", 200),
        (
            ["10-K", "10-Q"],
            "_ALL",
            "text/csv",  # Accept header must be multipart/mixed or application/json
            406,
        ),
        ([], "_ALL", "application/json", 400),
    ],
)
def test_section_narrative_api_with_headers(
    form_types, section, accept_header, response_status, tmpdir
):
    filenames = []
    for idx, form_type in enumerate(form_types):
        sample_document = generate_sample_document(form_type)
        filename = os.path.join(tmpdir.dirname, f"wilderness_{idx}.xbrl")
        with open(filename, "w") as f:
            f.write(sample_document)
        filenames.append(filename)

    # NOTE(robinson) - Reset the rate limit to avoid 429s in tests
    app.state.limiter.reset()
    client = TestClient(app)
    files = [
        ("text_files", (filename, open(filename, "rb"), "text/plain")) for filename in filenames
    ]
    response = client.post(
        SECTION_ROUTE,
        files=files,
        headers={
            "Accept": accept_header,
        },
        data={"section": [section]},
    )

    assert response.status_code == response_status


@pytest.mark.parametrize(
    "form_type, response_type, section",
    [
        ("10-K", "text/csv", "RISK_FACTORS"),
        ("10-Q", "text/csv", "RISK_FACTORS"),
        ("S-1", "text/csv", "RISK_FACTORS"),
        ("10-K", "text/csv", "_ALL"),
        ("10-Q", "text/csv", "_ALL"),
        ("S-1", "text/csv", "_ALL"),
    ],
)
def test_section_narrative_api_csv_response(form_type, response_type, section, tmpdir):
    sample_document = generate_sample_document(form_type)
    filename = os.path.join(tmpdir.dirname, "wilderness.xbrl")
    with open(filename, "w") as f:
        f.write(sample_document)

    # NOTE(robinson) - Reset the rate limit to avoid 429s in tests
    app.state.limiter.reset()
    client = TestClient(app)
    response = client.post(
        SECTION_ROUTE,
        files=[("text_files", (filename, open(filename, "rb"), "text/plain"))],
        data={"output_format": response_type, "section": [section]},
    )
    assert response.status_code == 200

    response_csv = csv.DictReader(StringIO(response.json()), delimiter=",")
    response_list = list(response_csv)

    assert [x["section"] for x in response_list]
    assert [x["element_type"] for x in response_list]
    assert [x["text"] for x in response_list]


def test_section_narrative_api_health_check():
    client = TestClient(app)
    response = client.get("/healthcheck")

    assert response.status_code == 200


def test_core_app_health_check():
    # NOTE(crag): switch all tests to core_app when rate limiting is removed
    client = TestClient(core_app)
    response = client.get("/healthcheck")

    assert response.status_code == 200
