<h3 align="center">
  <img src="img/unstructured_logo.png" height="200">
</h3>

<h3 align="center">
  <p>Pre-Processing Pipeline for SEC Filings</p>
</h3>


This repo implements a document pre-processing pipeline for SEC filings. Currently, the pipeline is capable of extracting narrative text from user-specified sections in 10-K, 10-Q, and S-1 filings.

The API is hosted at `https://api.unstructured.io`.

## Developer Quick Start

* Using `pyenv` to manage virtualenv's is recommended
	* Mac install instructions. See [here](https://github.com/Unstructured-IO/community#mac--homebrew) for more detailed instructions.
		* `brew install pyenv-virtualenv`
	  * `pyenv install 3.8.15`
  * Linux instructions are available [here](https://github.com/Unstructured-IO/community#linux).

* Create a virtualenv to work in and activate it, e.g. for one named `sec-filings`:

	`pyenv  virtualenv 3.8.15 sec-filings` <br />
	`pyenv activate sec-filings`

* Run `make install`
* Start a local jupyter notebook server with `make run-jupyter` <br />
	**OR** <br />
	just start the fast-API locally with `make run-web-app`

## Quick Tour

You can run this [Colab notebook](https://colab.research.google.com/drive/12mx7QE0Zm4jGB-3yTa9UBRhAsHU0ZScJ) to see how [pipeline-section.ipynb](/pipeline-notebooks/pipeline-section.ipynb) extracts the narrative text sections from an SEC Filing and defines an API.

## Extracting Narrative Text from an SEC Filing

To retrieve narrative text section(s) from an iXBRL S-1, 10-K, or 10-Q document (or amended version S-1/A, 10-K/A, or 10-Q/A), post the document to the `/section` API. You can try this out by downloading the sample documents using `make dl-test-artifacts`. Then, from
the `sample-sec-docs` folder, run:

```
curl -X 'POST' \
  'https://api.unstructured.io/sec-filings/v0.2.0/section' \
  -H 'accept: application/json' \
  -H 'Content-Type: multipart/form-data' \
  -F 'text_files=@rgld-10-K-85535-000155837021011343.xbrl' \
  -F section=RISK_FACTORS | jq -C . | less -R
```

Note that additional `-F section` parameters may be included in the curl request to fetch
multiple sections at once. Valid sections for [10-Ks](https://www.sec.gov/files/form10-k.pdf),
[10-Qs](https://www.sec.gov/files/form10-q.pdf), and [S-1s](https://www.sec.gov/files/forms-1.pdf)
are available on the SEC website. You can also reference
[this file](https://github.com/Unstructured-IO/pipeline-sec-filings/blob/main/prepline_sec_filings/sections.py)
for a list of valid `section` parameters, e.g. `RISK_FACTORS` OR `MANAGEMENT_DISCUSSION`.


You'll get back a response that looks like the following. Piping through `jq` and `less`
formats/colors the outputs and lets your scroll through the results.

```
{
  "RISK_FACTORS": [
    {
      "text": "You should carefully consider the risks described in this section. Our future performance is subject to risks and uncertainties that could have a material adverse effect on our business, results of operations, and financial condition and the trading price of our common stock. We may be subject to other risks and uncertainties not presently known to us. In addition, please see our note about forward-looking statements included in the MD&A.",
      "type": "NarrativeText"
    },
    {
      "text": "Our revenue is subject to volatility in metal prices, which could negatively affect our results of operations or cash flow.",
      "type": "NarrativeText"
    },
    {
      "text": "Market prices for gold, silver, copper, nickel, and other metals may fluctuate widely over time and are affected by numerous factors beyond our control. These factors include metal supply and demand, industrial and jewelry fabrication, investment demand, central banking actions, inflation expectations, currency values, interest rates, forward sales by metal producers, and political, trade, economic, or banking conditions.",
      "type": "NarrativeText"
    },
    ...
  ]
}
```


You can also pass in custom section regex patterns using the `section_regex` parameter. For
example, you can run the following command to request the risk factors section:

```
curl -X 'POST' \
  'http://localhost:8000/sec-filings/v0.2.0/section' \
  -H 'accept: application/json' \
  -H 'Content-Type: multipart/form-data' \
  -F 'text_files=@rgld-10-K-85535-000155837021011343.xbrl' \
  -F 'section_regex=risk factors'  | jq -C . | less -R
```

The result will be:

```
{
  "REGEX_0": [
    {
      "text": "You should carefully consider the risks described in this section. Our future performance is subject to risks and uncertainties that could have a material adverse effect on our business, results of operations, and financial condition and the trading price of our common stock. We may be subject to other risks and uncertainties not presently known to us. In addition, please see our note about forward-looking statements included in the MD&A.",
      "type": "NarrativeText"
    },
    {
      "text": "Our revenue is subject to volatility in metal prices, which could negatively affect our results of operations or cash flow.",
      "type": "NarrativeText"
    },
    {
      "text": "Market prices for gold, silver, copper, nickel, and other metals may fluctuate widely over time and are affected by numerous factors beyond our control. These factors include metal supply and demand, industrial and jewelry fabrication, investment demand, central banking actions, inflation expectations, currency values, interest rates, forward sales by metal producers, and political, trade, economic, or banking conditions.",
      "type": "NarrativeText"
    },
    ...
  ]
}
```

As with the `section` parameter, you can request multiple regexes by passing in multiple values
for the `section_regex` parameter. The requested pattern will be treated as a raw string.

You can also use special regex characters in your pattern, as shown in the example below:

```
 curl -X 'POST' \
  'http://localhost:8000/sec-filings/v0.2.0/section' \
  -H 'accept: application/json' \
  -H 'Content-Type: multipart/form-data' \
  -F 'text_files=@rgld-10-K-85535-000155837021011343.xbrl' \
  -F "section_regex=^(\S+\W?)+$"
```

### Helper functions for SEC EDGAR API

You can use some of the functions provided in `prepline_sec_filings.fetch` to directly view or manipulate the filings available from the SEC's [EDGAR API](https://www.sec.gov/edgar/searchedgar/companysearch.html).
For example, `get_filing(cik, accession_number, your_organization_name, your_email)` will return the text of the filing with accession number `accession_number` for the organization with CIK number `cik`.
`your_organization_name` and `your_email` should be your information.
The parameters `your_organization_name` and `your_email` are passed along to Edgar's API to identify the caller and are required by Edgar.
Alternatively, the parameters may be omitted if the environment variables `SEC_API_ORGANIZATION` and `SEC_API_EMAIL` are defined.


Helper functions are also provided for cases where the CIK and/or accession numbers are not known. For example,
`get_form_by_ticker('mmm', '10-K', your_organization_name, your_email)` returns the text of the latest 10-K filing from 3M,
and `open_form_by_ticker('mmm', '10-K', your_organization_name, your_email)` opens the SEC index page for the same filing in a web browser.

### Generating Python files from the pipeline notebooks

The python module [section.py](/prepline_sec_filings/api/section.py) contains the FASTApi code needed to serve the API. It's created with `make generate-api`, which derives the API from the notebook [pipeline-section.ipynb](/pipeline-notebooks/pipeline-section.ipynb).

You can generate the FastAPI APIs from all [pipeline-notebooks/](/pipeline-notebooks) by running `make generate-api`.

## Docker

It is not necessary to run Docker in a local development environment, however a Dockerfile and
make targets of `docker-build`, `docker-start-api`, and `docker-start-jupyter` are provided for convenience.

You can also launch a Jupyter instance to try out the notebooks with [![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/Unstructured-IO/pipeline-sec-filings/HEAD).

## Security Policy

See our [security policy](https://github.com/Unstructured-IO/pipeline-sec-filings/security/policy) for
information on how to report security vulnerabilities.

## Learn more

| Section | Description |
|-|-|
| [Company Website](https://unstructured.io) | Unstructured.io product and company info |
[EDGAR API](https://www.sec.gov/edgar/searchedgar/companysearch.html) | Documentation for the SEC
| [10-K Filings](https://www.sec.gov/files/form10-k.pdf) | Detailed documentation on 10-K filings |
| [10-Q Filings](https://www.sec.gov/files/form10-q.pdf) | Detailed documentation on 10-Q filings |
| [S-1 Filings](https://www.sec.gov/files/forms-1.pdf) | Detailed documentation on S-1 filings |
