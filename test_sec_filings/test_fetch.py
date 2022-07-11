import json
import os
import webbrowser
import requests
from unittest import mock

import pytest
import prepline_sec_filings.fetch as fetch


response_content = {
    "filings": {
        "recent": {
            "accessionNumber": [
                "1234567890-12-345678",
                "1234567890-12-345679",
                "1234567890-12-345680",
                "1234567890-12-345681",
            ],
            "form": ["10-K", "S-1", "10-K", "10-Q"],
        }
    }
}


class MockSession:
    def __init__(self):
        self.headers = dict()

    def get(self, url, **kwargs):
        if url.startswith(fetch.SEC_ARCHIVE_URL):
            if url.endswith("txt"):
                filename = url.split("/")[-1]
                return MockResponse(f"<SEC-DOCUMENT>{filename}</SEC-DOCUMENT>")
            elif url.endswith("html"):
                return MockResponse("<html></html>")
        elif url.startswith(fetch.SEC_SEARCH_URL):
            return MockResponse("<html><body>CIK=1234567890</body></html>")
        elif url.startswith(fetch.SEC_SUBMISSIONS_URL):
            return MockResponse(
                "",
                content=json.dumps(response_content),
            )
        else:
            raise ValueError


class MockResponse:
    def __init__(self, text, content=None):
        self.text = text
        self.content = content

    def raise_for_status(self):
        pass


def test_get_filing(monkeypatch):
    monkeypatch.setattr(requests, "Session", MockSession)
    filing = fetch.get_filing("949874", "000119312511215661", "Giant", "parker@giant.com")
    assert filing == "<SEC-DOCUMENT>0001193125-11-215661.txt</SEC-DOCUMENT>"


def test_archive_url():
    url = fetch.archive_url("949874", "000119312511215661")
    assert url == f"{fetch.SEC_ARCHIVE_URL}/949874/000119312511215661/0001193125-11-215661.txt"


def test_add_dashes():
    accession_number = fetch._add_dashes("000119312511215661")
    assert accession_number == "0001193125-11-215661"


def test_drop_dashes():
    accession_number = fetch._drop_dashes("0001193125-11-215661")
    assert accession_number == "000119312511215661"


def test_get_session(monkeypatch):
    monkeypatch.setattr(requests, "Session", MockSession)
    session = fetch._get_session("Giant", "parker@giant.com")
    assert session.headers["User-Agent"] == "Giant parker@giant.com"


@mock.patch.dict(
    os.environ,
    {"SEC_API_ORGANIZATION": "OtherOrg", "SEC_API_EMAIL": "person@otherorg.io"},
)
def test_get_session_default(monkeypatch):
    monkeypatch.setattr(requests, "Session", MockSession)
    session = fetch._get_session()
    assert session.headers["User-Agent"] == "OtherOrg person@otherorg.io"


def test_get_cik_by_ticker(monkeypatch):
    monkeypatch.setattr(requests, "Session", MockSession)
    session = MockSession()
    cik = fetch.get_cik_by_ticker(session, "noice")
    assert cik == "1234567890"


def test_get_forms_by_cik(monkeypatch):
    monkeypatch.setattr(requests, "Session", MockSession)
    session = MockSession()
    forms = fetch.get_forms_by_cik(session, "1234567890")
    assert forms["1234567890-12-345678"] == "10-K"
    assert forms["1234567890-12-345679"] == "S-1"
    assert forms["1234567890-12-345680"] == "10-K"
    assert forms["1234567890-12-345681"] == "10-Q"


def test_get_recent_acc_num_by_cik(monkeypatch):
    monkeypatch.setattr(requests, "Session", MockSession)
    session = MockSession()
    assert fetch._get_recent_acc_num_by_cik(session, "1234567890", ["10-K"]) == (
        "123456789012345678",
        "10-K",
    )
    assert fetch._get_recent_acc_num_by_cik(session, "1234567890", ["S-1"]) == (
        "123456789012345679",
        "S-1",
    )
    assert fetch._get_recent_acc_num_by_cik(session, "1234567890", ["10-Q"]) == (
        "123456789012345681",
        "10-Q",
    )


@pytest.mark.parametrize(
    "form_type, expected",
    [
        ("10-K", "<SEC-DOCUMENT>1234567890-12-345678.txt</SEC-DOCUMENT>"),
        ("10-Q", "<SEC-DOCUMENT>1234567890-12-345681.txt</SEC-DOCUMENT>"),
        ("S-1", "<SEC-DOCUMENT>1234567890-12-345679.txt</SEC-DOCUMENT>"),
    ],
)
def test_get_form_by_ticker(monkeypatch, form_type, expected):
    monkeypatch.setattr(requests, "Session", MockSession)
    assert (
        fetch.get_form_by_ticker("1234567890", form_type, company="Giant", email="parker@giant.com")
        == expected
    )


@pytest.mark.parametrize(
    "form_type, expected",
    [
        (
            "10-K",
            f"{fetch.SEC_ARCHIVE_URL}/1234567890/123456789012345678/"
            "1234567890-12-345678-index.html",
        ),
        (
            "10-Q",
            f"{fetch.SEC_ARCHIVE_URL}/1234567890/123456789012345681/"
            "1234567890-12-345681-index.html",
        ),
        (
            "S-1",
            f"{fetch.SEC_ARCHIVE_URL}/1234567890/123456789012345679/"
            "1234567890-12-345679-index.html",
        ),
    ],
)
@mock.patch("webbrowser.open_new_tab")
@mock.patch("requests.Session", MockSession)
def test_open_form_by_ticker(monkeypatch, form_type, expected):
    fetch.open_form_by_ticker("noice", form_type, False, company="Giant", email="parker@giant.com")
    webbrowser.open_new_tab.assert_called_once_with(expected)


@pytest.mark.parametrize(
    "cik, acc_num, expected",
    [
        (
            "1234567890",
            "123456789012345678",
            f"{fetch.SEC_ARCHIVE_URL}/1234567890/123456789012345678/"
            "1234567890-12-345678-index.html",
        ),
        (
            "1234567890",
            "123456789012345681",
            f"{fetch.SEC_ARCHIVE_URL}/1234567890/123456789012345681/"
            "1234567890-12-345681-index.html",
        ),
        (
            "1234567890",
            "123456789012345679",
            f"{fetch.SEC_ARCHIVE_URL}/1234567890/123456789012345679/"
            "1234567890-12-345679-index.html",
        ),
    ],
)
@mock.patch("webbrowser.open_new_tab")
@mock.patch("requests.Session", MockSession)
def test_open_form(monkeypatch, cik, acc_num, expected):
    fetch.open_form(cik, acc_num)
    webbrowser.open_new_tab.assert_called_once_with(expected)
