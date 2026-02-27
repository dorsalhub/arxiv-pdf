# Copyright 2026 Dorsal Hub LTD
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import pathlib
import tomllib
import pytest
from unittest.mock import MagicMock, patch

from dorsal.testing import run_model
from arxiv_pdf.model import ArxivPdf

# Load the project configuration
root = pathlib.Path(__file__).parent.parent
with open(root / "model_config.toml", "rb") as f:
    config = tomllib.load(f)


@pytest.fixture
def dummy_pdf(tmp_path):
    """
    Creates a temporary file with valid PDF magic bytes.
    This ensures Dorsal's libmagic pre-flight check detects it as 'application/pdf'
    and passes the media_type dependency check.
    """
    file_path = tmp_path / "dummy_paper.pdf"
    file_path.write_bytes(b"%PDF-1.4\n%EOF\n")
    return str(file_path)


@patch("arxiv_pdf.model.get_file_annotation")
@patch("arxiv_pdf.model.identify_file")
def test_arxiv_pdf_success(mock_identify_file, mock_get_annotation, dummy_pdf):
    """Tests the happy path where a file is successfully identified and fetched."""

    # 1. Setup the identify_file mock
    mock_stub = MagicMock()
    mock_stub.id = "fake-uuid-1234"

    mock_file_record = MagicMock()
    mock_file_record.annotations = [
        ("file_base", [MagicMock()]),
        ("dorsal/arxiv", [mock_stub]),  # The stub we are looking for
    ]
    mock_identify_file.return_value = mock_file_record

    # 2. Setup the get_file_annotation mock
    mock_full_annotation = MagicMock()
    mock_full_annotation.record = {
        "arxiv_id": "2405.06604v1",
        "title": "A Great Paper",
        "abstract": "This is a great abstract.",
        "authors": ["Alice", "Bob"],
    }
    mock_get_annotation.return_value = mock_full_annotation

    # Run the model using the dynamically generated dummy PDF
    result = run_model(
        annotation_model=ArxivPdf,
        file_path=dummy_pdf,
        schema_id=config["schema_id"],
        validation_model=config.get("validation_model"),
        dependencies=config.get("dependencies"),
        options=config.get("options"),
    )

    # Assertions
    assert result.error is None
    assert result.record is not None
    assert result.record["arxiv_id"] == "2405.06604v1"
    assert result.record["title"] == "A Great Paper"


@patch("arxiv_pdf.model.identify_file")
def test_arxiv_pdf_identify_api_failure(mock_identify_file, dummy_pdf):
    """Tests the model gracefully handling an API crash during identification."""

    mock_identify_file.side_effect = Exception("Dorsal API is offline")

    result = run_model(
        annotation_model=ArxivPdf,
        file_path=dummy_pdf,
        schema_id=config["schema_id"],
    )

    assert result.record is None
    assert result.error is not None
    assert "Failed to identify file with DorsalHub API" in result.error


@patch("arxiv_pdf.model.identify_file")
def test_arxiv_pdf_no_arxiv_record(mock_identify_file, dummy_pdf):
    """Tests the model correctly rejecting a file that exists but lacks arxiv metadata."""

    mock_file_record = MagicMock()
    mock_file_record.annotations = [("file_base", [MagicMock()]), ("dorsal/arxiv", [])]
    mock_identify_file.return_value = mock_file_record

    result = run_model(
        annotation_model=ArxivPdf,
        file_path=dummy_pdf,
        schema_id=config["schema_id"],
    )

    assert result.record is None
    assert result.error is not None
    assert "No dorsal/arxiv annotation found for this file" in result.error


@patch("arxiv_pdf.model.get_file_annotation")
@patch("arxiv_pdf.model.identify_file")
def test_arxiv_pdf_fetch_annotation_failure(
    mock_identify_file, mock_get_annotation, dummy_pdf
):
    """Tests the model gracefully handling a failure when fetching the full record."""

    mock_stub = MagicMock()
    mock_stub.id = "fake-uuid-1234"
    mock_file_record = MagicMock()
    mock_file_record.annotations = [("dorsal/arxiv", [mock_stub])]
    mock_identify_file.return_value = mock_file_record

    mock_get_annotation.side_effect = Exception("Record deleted or unavailable")

    result = run_model(
        annotation_model=ArxivPdf,
        file_path=dummy_pdf,
        schema_id=config["schema_id"],
    )

    assert result.record is None
    assert result.error is not None
    assert "Failed to fetch full annotation fake-uuid-1234" in result.error
