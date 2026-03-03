# arXiv PDF Info

A Dorsal inference model for identifying [arXiv](https://arxiv.org/) preprints. 

This model hashes your local PDF and fetches structured metadata (Title, Authors, Abstract, Categories, etc.) from DorsalHub.

## Useful For

- Identifying arXiv PDFs
- Generating citations

## Compatibility

* **Python:** 3.11, 3.12, 3.13, 3.14
* **Dependencies:** Requires `dorsalhub`.

## Quick Start

Run the model directly against a local PDF file (downloads and installs if not already installed):

```bash
dorsal run dorsalhub/arxiv-pdf ./2405.06604v1.pdf
```

### Output Formats & Exporting

You can export to a number of formats from the CLI:

#### Example: Export to BibTeX (`bibtex`) citation:

```console
$ dorsal run dorsalhub/arxiv-pdf ./2405.06604v1.pdf --export=bibtex
@misc{2405_06604,
  title = {Explaining Text Similarity in Transformer Models},
  author = {Alexandros Vasileiou and Oliver Eberle},
  eprint = {2405.06604},
  archivePrefix = {arXiv},
  primaryClass = {cs.CL},
  url = {[https://arxiv.org/abs/2405.06604](https://arxiv.org/abs/2405.06604)},
  year = {2024}
}
```

#### Example: Export a RIS (`ris`) citation:

```console
$ dorsal run dorsalhub/arxiv-pdf ./2405.06604v1.pdf --export=ris
TY  - PREP
T1  - Explaining Text Similarity in Transformer Models
AU  - Alexandros Vasileiou
AU  - Oliver Eberle
AB  - As Transformers have become state-of-the-art models for natural language...
PY  - 2024
KW  - cs.CL
KW  - cs.LG
UR  - [https://arxiv.org/abs/2405.06604](https://arxiv.org/abs/2405.06604)
M3  - 2405.06604
ER  - 
```

#### Example: Export to Markdown (`md`):

```console
$ dorsal run dorsalhub/arxiv-pdf ./2405.06604v1.pdf --export=md
---
arxiv_id: 2405.06604
year: 2024
categories: [cs.CL, cs.LG]
---

# Explaining Text Similarity in Transformer Models

**Authors:** Alexandros Vasileiou, Oliver Eberle

## Abstract
As Transformers have become state-of-the-art models for natural language...
```


## Development

### Running Tests

We use `pytest` for unit testing.:

```bash
pip install -e ".[dev]"
pytest --cov=arxiv_pdf tests/
```

Or via [`uv`](https://docs.astral.sh/uv/):
```bash
uv run pytest
```


## License

This project is open source and provided under the Apache 2.0 license.
