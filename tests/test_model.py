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
import uuid
import pytest
from unittest.mock import patch

from dorsal.testing import run_model
from arxiv_pdf.model import ArxivPdf

from dorsal.file.validators.file_record import FileRecord, AnnotationStub
from dorsal.client.validators import FileAnnotationResponse
from dorsal.file.configs.model_runner import RunModelResult
from dorsal.common.exceptions import NotFoundError

root = pathlib.Path(__file__).parent.parent
with open(root / "model_config.toml", "rb") as f:
    config = tomllib.load(f)


@pytest.fixture
def dummy_pdf(tmp_path):
    file_path = tmp_path / "dummy_paper.pdf"
    file_path.write_bytes(b"%PDF-1.4\n%EOF\n")
    return str(file_path)


class FakeAnnotations:
    def __init__(self, schemas):
        self.schemas = schemas

    def __iter__(self):
        return iter(self.schemas)


def create_mock_file_record(has_arxiv=True):
    if has_arxiv:
        stub = AnnotationStub.model_construct(id=uuid.uuid4())
        annotations = FakeAnnotations([("file_base", []), ("dorsal/arxiv", [stub])])
    else:
        annotations = FakeAnnotations([("file_base", [])])
    return FileRecord.model_construct(annotations=annotations)


def create_mock_pdf_result(title=None):
    record = {"title": title} if title else {}
    return RunModelResult.model_construct(record=record, error=None)


@patch("arxiv_pdf.model.get_file_annotation")
@patch("arxiv_pdf.model.identify_file")
def test_arxiv_pdf_binary_hit(mock_identify, mock_get_ann, dummy_pdf):
    """Tests the fast path: exact binary match."""
    mock_identify.return_value = create_mock_file_record(has_arxiv=True)
    mock_get_ann.return_value = FileAnnotationResponse.model_construct(
        record={"arxiv_id": "2405.06604v1", "title": "A Great Paper"}
    )

    result = run_model(ArxivPdf, dummy_pdf, schema_id=config["schema_id"])

    assert result.error is None
    assert result.record["arxiv_id"] == "2405.06604v1"


@patch("arxiv_pdf.model.get_file_annotation")
@patch("arxiv_pdf.model.get_dorsal_file_record")
@patch("arxiv_pdf.model.run_model")
@patch("arxiv_pdf.model.identify_file")
def test_arxiv_pdf_title_fallback(
    mock_identify, mock_run_model, mock_get_record, mock_get_ann, dummy_pdf
):
    """Tests fallback to virtual hash via PDF title."""
    mock_identify.side_effect = NotFoundError("No binary match")
    mock_run_model.return_value = create_mock_pdf_result(
        title="arXiv:astro-ph/9912160v1"
    )

    mock_get_record.return_value = create_mock_file_record(has_arxiv=True)
    mock_get_ann.return_value = FileAnnotationResponse.model_construct(
        record={"arxiv_id": "astro-ph/9912160"}
    )

    result = run_model(ArxivPdf, dummy_pdf, schema_id=config["schema_id"])

    assert result.error is None
    assert result.record["arxiv_id"] == "astro-ph/9912160"
    mock_get_record.assert_called_once()


@patch("arxiv_pdf.model.get_file_annotation")
@patch("arxiv_pdf.model.get_dorsal_file_record")
@patch("arxiv_pdf.model.run_model")
@patch("arxiv_pdf.model.identify_file")
def test_arxiv_pdf_filename_fallback(
    mock_identify, mock_run_model, mock_get_record, mock_get_ann, tmp_path
):
    """Tests fallback to virtual hash via filename."""
    file_path = tmp_path / "2405.06604v1.pdf"
    file_path.write_bytes(b"%PDF-1.4\n%EOF\n")

    mock_identify.side_effect = NotFoundError("No binary match")
    mock_run_model.return_value = create_mock_pdf_result(title=None)

    mock_get_record.return_value = create_mock_file_record(has_arxiv=True)
    mock_get_ann.return_value = FileAnnotationResponse.model_construct(
        record={"arxiv_id": "2405.06604"}
    )

    result = run_model(ArxivPdf, str(file_path), schema_id=config["schema_id"])

    assert result.error is None
    assert result.record["arxiv_id"] == "2405.06604"
    mock_get_record.assert_called_once()


@patch("arxiv_pdf.model.run_model")
@patch("arxiv_pdf.model.identify_file")
def test_arxiv_pdf_conflicting_heuristics(mock_identify, mock_run_model, tmp_path):
    """Tests safe exit when title and filename disagree."""
    file_path = tmp_path / "2405.06604v1.pdf"
    file_path.write_bytes(b"%PDF-1.4\n%EOF\n")

    mock_identify.side_effect = NotFoundError("No binary match")
    mock_run_model.return_value = create_mock_pdf_result(title="arXiv:1706.03762v1")

    result = run_model(ArxivPdf, str(file_path), schema_id=config["schema_id"])

    assert result.record is None
    assert "Conflicting arXiv IDs found" in result.error


@patch("arxiv_pdf.model.identify_file")
def test_arxiv_pdf_strict_mode(mock_identify, dummy_pdf):
    """Tests that strict mode prevents heuristic fallbacks."""
    mock_identify.side_effect = NotFoundError("No binary match")

    result = run_model(
        ArxivPdf, dummy_pdf, schema_id=config["schema_id"], options={"strict": True}
    )

    assert result.record is None
    assert "Strict mode enabled" in result.error


@patch("arxiv_pdf.model.identify_file")
def test_arxiv_pdf_api_failure_handled(mock_identify, dummy_pdf):
    """Tests that an unexpected API crash is safely handled."""
    mock_identify.side_effect = Exception("API is completely offline")

    result = run_model(ArxivPdf, dummy_pdf, schema_id=config["schema_id"])

    assert result.record is None
    assert "API is completely offline" in result.error


@patch("arxiv_pdf.model.get_file_annotation")
@patch("arxiv_pdf.model.get_dorsal_file_record")
@patch("arxiv_pdf.model.run_model")
@patch("arxiv_pdf.model.identify_file")
def test_arxiv_pdf_no_filename(
    mock_identify, mock_run_model, mock_get_record, mock_get_ann, dummy_pdf
):
    """Tests fallback behavior when the file has no valid name."""
    mock_identify.side_effect = NotFoundError("No binary match")
    mock_run_model.return_value = create_mock_pdf_result(title="arXiv:1234.56789v1")
    mock_get_record.return_value = create_mock_file_record(has_arxiv=True)
    mock_get_ann.return_value = FileAnnotationResponse.model_construct(
        record={"arxiv_id": "1234.56789"}
    )

    with patch("arxiv_pdf.model.ArxivPdf.name", create=True) as mock_name:
        mock_name.return_value = None
        result = run_model(ArxivPdf, dummy_pdf, schema_id=config["schema_id"])

        assert result.error is None
        assert result.record["arxiv_id"] == "1234.56789"


@patch("arxiv_pdf.model.get_file_annotation")
@patch("arxiv_pdf.model.identify_file")
@patch("arxiv_pdf.model.run_model")
def test_arxiv_pdf_fetch_annotation_failure(
    mock_run_model, mock_identify, mock_get_ann, dummy_pdf
):
    """Tests gracefully handling an API crash when fetching the exact annotation."""
    mock_identify.return_value = create_mock_file_record(has_arxiv=True)

    mock_run_model.return_value = create_mock_pdf_result(title="arXiv:1234.56789v1")
    mock_get_ann.side_effect = Exception("Database error")

    result = run_model(ArxivPdf, dummy_pdf, schema_id=config["schema_id"])
    assert "Failed to fetch annotation" in result.error


@patch("arxiv_pdf.model.run_model")
@patch("arxiv_pdf.model.identify_file")
def test_arxiv_pdf_binary_hit_no_annotation_fallback_fails(
    mock_identify, mock_run_model, tmp_path
):
    """Tests binary hit without arxiv data, falling back to heuristics which also fail."""
    file_path = tmp_path / "random_file.pdf"
    file_path.write_bytes(b"%PDF-1.4\n%EOF\n")

    mock_identify.return_value = create_mock_file_record(has_arxiv=False)

    mock_run_model.return_value = create_mock_pdf_result(title=None)

    result = run_model(ArxivPdf, str(file_path), schema_id=config["schema_id"])
    assert result.record is None
    assert "Unable to infer arXiv ID" in result.error


@patch("arxiv_pdf.model.get_dorsal_file_record")
@patch("arxiv_pdf.model.run_model")
@patch("arxiv_pdf.model.identify_file")
def test_arxiv_pdf_virtual_hash_not_found(
    mock_identify, mock_run_model, mock_get_record, dummy_pdf
):
    """Tests safe exit when virtual hash is not indexed on DorsalHub."""
    mock_identify.side_effect = NotFoundError("No binary match")
    mock_run_model.return_value = create_mock_pdf_result(title="arXiv:1234.56789v1")
    mock_get_record.side_effect = NotFoundError("Not on DorsalHub")

    result = run_model(ArxivPdf, dummy_pdf, schema_id=config["schema_id"])
    assert "Virtual hash for ArXiv ID" in result.error


@patch("arxiv_pdf.model.get_dorsal_file_record")
@patch("arxiv_pdf.model.run_model")
@patch("arxiv_pdf.model.identify_file")
def test_arxiv_pdf_virtual_hash_api_error(
    mock_identify, mock_run_model, mock_get_record, dummy_pdf
):
    """Tests safe exit when API crashes during virtual hash query."""
    mock_identify.side_effect = NotFoundError("No binary match")
    mock_run_model.return_value = create_mock_pdf_result(title="arXiv:1234.56789v1")
    mock_get_record.side_effect = Exception("API Offline")

    result = run_model(ArxivPdf, dummy_pdf, schema_id=config["schema_id"])
    assert "API Offline" in result.error


@patch("arxiv_pdf.model.get_dorsal_file_record")
@patch("arxiv_pdf.model.run_model")
@patch("arxiv_pdf.model.identify_file")
def test_arxiv_pdf_virtual_hash_missing_annotation(
    mock_identify, mock_run_model, mock_get_record, dummy_pdf
):
    """Tests virtual hash hit, but it lacks the dorsal/arxiv annotation."""
    mock_identify.side_effect = NotFoundError("No binary match")
    mock_run_model.return_value = create_mock_pdf_result(title="arXiv:1234.56789v1")

    mock_get_record.return_value = create_mock_file_record(has_arxiv=False)

    result = run_model(ArxivPdf, dummy_pdf, schema_id=config["schema_id"])
    assert "Virtual hash found, but lacks dorsal/arxiv annotation" in result.error


@patch("arxiv_pdf.model.identify_file")
def test_arxiv_pdf_early_exit_no_filename(mock_identify):
    """Tests that the model gracefully exits if the filename cannot be determined."""

    mock_identify.side_effect = NotFoundError("No binary match")

    model = ArxivPdf("/tmp/dummy_paper.pdf")
    model.name = None

    with patch.object(model, "log_debug") as mock_log:
        with patch.object(
            model, "extract_arxiv_id_from_pdf_title", return_value=(None, None)
        ):
            result = model.main()

            assert result is None

            mock_log.assert_any_call("Unable to determine filename")


@patch("arxiv_pdf.model.get_file_annotation")
@patch("arxiv_pdf.model.get_dorsal_file_record")
@patch("arxiv_pdf.model.run_model")
@patch("arxiv_pdf.model.identify_file")
def test_arxiv_pdf_virtual_hash_annotation_fetch_failure(
    mock_identify, mock_run_model, mock_get_record, mock_get_ann, dummy_pdf
):
    """Tests that an API crash during virtual hash annotation hydration preserves the error state."""

    mock_identify.side_effect = NotFoundError("No binary match")

    mock_run_model.return_value = create_mock_pdf_result(title="arXiv:1234.56789v1")

    mock_get_record.return_value = create_mock_file_record(has_arxiv=True)

    mock_get_ann.side_effect = Exception("Database error on virtual hash hydration")

    result = run_model(ArxivPdf, dummy_pdf, schema_id=config["schema_id"])

    assert result.record is None
    assert "Failed to fetch annotation" in result.error
