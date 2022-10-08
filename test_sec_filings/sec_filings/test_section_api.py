import os
import pytest

from fastapi.testclient import TestClient

from unstructured_api_tools.pipelines.api_conventions import get_pipeline_path

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
        files={"file": (filename, open(filename, "rb"), "text/plain")},
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
        files={"file": (filename, open(filename, "rb"), "text/plain")},
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
        files={"file": (filename, open(filename, "rb"), "text/plain")},
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
    "form_type, section",
    [
        ("10-K", "RISK_FACTORS"),
    ],
)
def test_section_narrative_api_with_wrong_media_type(form_type, section, tmpdir):
    sample_document = generate_sample_document(form_type)
    filename = os.path.join(tmpdir.dirname, "wilderness.xbrl")
    with open(filename, "w") as f:
        f.write(sample_document)

    app.state.limiter.reset()
    client = TestClient(app)
    response = client.post(
        SECTION_ROUTE,
        files={"file": (filename, open(filename, "rb"), "text/plain")},
        data={"section": [section]},
        headers={"accept": "wrong/media_type"},
    )

    assert response.status_code == 415


@pytest.mark.parametrize(
    "form_type, section",
    [
        ("10-K", "RISK_FACTORS"),
    ],
)
def test_section_narrative_api_with_confict_media_type(form_type, section, tmpdir):
    sample_document = generate_sample_document(form_type)
    filename = os.path.join(tmpdir.dirname, "wilderness.xbrl")
    with open(filename, "w") as f:
        f.write(sample_document)

    app.state.limiter.reset()
    client = TestClient(app)
    response = client.post(
        SECTION_ROUTE,
        files={"file": (filename, open(filename, "rb"), "text/plain")},
        data={"section": [section]},
        headers={"accept": "text/csv"},
    )

    assert response.status_code == 409


def test_section_narrative_api_healt_check():
    client = TestClient(app)
    response = client.get("./healthcheck")

    assert response.status_code == 200
