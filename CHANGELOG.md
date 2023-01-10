## 0.2.1-dev

* Allows a json list instead of a multipart response for multi-file requests
* Supports text/csv responses instead of just json
* More general (non-pipeline-specific) way of starting the app
* Add alternative way of importing `Final` to support google colab
* Dependency bumps

## 0.2.0

* Updated section API to accept multiple text files uploads as `text_files` parameter.

## 0.1.0

* Updated FastAPI param m_section -> section
* API updated to support known filing sections rather just risk factors
* Updated interface to be compatible with new version of unstructured

## 0.0.3

* Updated `match_s1_toc_title_to_section` for an exact match
* Enumerated and added patterns for common 10-K/Q and S-1 sections
* Refactor get risk narrative to allow capture of variable section
* Naming conventions updated with "pipeline" terminology (no longer "recipe")
* Various tweaks to parsing methods to improve capturing of risk section and TOC
* Auto-generated api risk_narrative.py now lints (unstructured-api-tools)
* Added get_table_of_contents to find TOC elements within SEC document (and tests)
* Added helper functions for retrieving/opening documents from the SEC
* Changed `unstructured_api` package to `unstructured_api_tools`
* Rewrote `get_risk_narrative` to use the TOC
* Added integration tests to verify capture of risk factors section

## 0.0.2

* Pipeline now generates a FastAPI web application
* Added logic to skip risk section if risk section is empty upon completion
* Added different form types to unit tests, and added variation of forms that use a table of contents

## 0.0.1

* Added make target to build the pipeline scripts
* Change `doc_prep` package name to `unstructured`
* Created pipeline for extracting the risk section from 10-K, 10-Q, and S-1 filings
* Initial repo setup for SEC filings
