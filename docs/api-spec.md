## SEC Filings Pipeline API Specification

This document outlines the specification for the section extraction endpoint for SEC
document. The goal is for users to request one or more sections from and SEC filing
and receive each of those sections back in the API response.


### Request

The following is the format for the `curl` request. In the API definition function,
the section has the type `List[str]`. Users can request one or multiple sections from the API.

```
curl -X POST  "<base-url>/sec-filings/v0.0.1/sections" \
	-H 'accept: application/json' \
  -H 'Content-Type: multipart/form-data' \
	-F 'section=risk factors' \
	-F 'section=dilution' \
  -F 'file=@rgld-10-K-85535-000155837021011343.xbrl' | jq -C . | less -R
```

Currently, only the API only supports uploading a single doucments. The API will support multiple
documents in the future.


### Response

The response from the API should look like:

```json
[
	{
		"section_name": "<section1>",
		"found": true,
		"elements": [
				{
					"text": "<text>",
					"id": "<id>",
					"type": "<title|narrative_text>",
				}
		], ...
	},
	{
		"section_name": "<section2>",
		"found": false,
		"elements": []
	},
]
```

If the request includes a section that does not validate against
[`sections.py`](https://github.com/Unstructured-IO/pipeline-sec-filings/blob/main/prepline_sec_filings/sections.py),
the API should respond with `422: Unprocessable Entity` and a message indicating which
section names did not validate.
