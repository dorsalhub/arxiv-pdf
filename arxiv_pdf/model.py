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

import hashlib
import re

from importlib.metadata import version

from dorsal import AnnotationModel
from dorsal.api.file import identify_file, get_file_annotation, get_dorsal_file_record
from dorsal.api.model import run_model
from dorsal.common.exceptions import NotFoundError
from dorsal.client.validators import FileAnnotationResponse
from dorsal.file.annotation_models.pdf.model import PDFAnnotationModel
from dorsal.file.validators.pdf import PDFValidationModel
from dorsal.file.validators.file_record import AnnotationStub, FileRecord

# 1. Modern IDs in Title (e.g., arXiv:2405.06604v1)
RX_TITLE_MODERN = re.compile(r"arXiv:(\d{4}\.\d{4,5})(v\d+)?")

# 2. Legacy IDs in Title (e.g., arXiv:astro-ph/9912160)
RX_TITLE_LEGACY = re.compile(r"arXiv:([a-zA-Z\-]+/\d{7})(v\d+)?")

# 3. Modern IDs in Filename
RX_FILENAME_MODERN = re.compile(
    r"(?:^|[\s_])(\d{4}\.\d{4,5})(v\d+)?\.pdf$", re.IGNORECASE
)


class ArxivPdf(AnnotationModel):
    id = "github:dorsalhub/dorsal-arxiv"
    version = version("dorsal-arxiv-pdf")

    def extract_arxiv_id_from_pdf_title(self) -> tuple[str | None, str | None]:
        pdf_title: str | None = None
        arxiv_id: str | None = None

        result = run_model(
            annotation_model=PDFAnnotationModel,
            file_path=self.file_path,
            validation_model=PDFValidationModel,
        )
        record = result.record

        if record and (pdf_title := record.get("title")):
            if m := RX_TITLE_MODERN.search(pdf_title):
                arxiv_id = m.group(1)
            elif m := RX_TITLE_LEGACY.search(pdf_title):
                arxiv_id = m.group(1)

        return pdf_title, arxiv_id

    def extract_arxiv_id_from_file_name(self) -> str | None:
        if self.name is None:
            self.log_debug("Unable to determine filename")
            return None

        m = RX_FILENAME_MODERN.search(self.name)
        if m:
            return m.group(1)

        self.log_debug(f"Could not extract arXiv ID from filename: '{self.name}'")
        return None

    def _hash_arxiv_id(self, arxiv_id: str) -> str:
        """Hashes an arXiv ID into SHA-256 hex string.

        E.g. "2405.06604" -> "251814221b69665d6054735dbe4cfddc048ddcd40d677f6c89757d2fa88dd6b2"
        """
        self.log_debug(f"Hashing arXiv ID: {arxiv_id}")
        arxiv_id_bytes = arxiv_id.encode("utf-8")
        return hashlib.sha256(arxiv_id_bytes).hexdigest()

    def retrieve_arxiv_annotation(
        self, file_record: FileRecord
    ) -> FileAnnotationResponse | None:
        self.log_debug("Checking for dorsal/arxiv annotation stub...")
        arxiv_annotation_stub: AnnotationStub | None = None

        if file_record.annotations:
            for schema, record in file_record.annotations:
                if schema == "dorsal/arxiv":
                    if record and len(record) > 0:
                        arxiv_annotation_stub = record[0]
                    break

        if arxiv_annotation_stub:
            self.log_debug(
                f"Found dorsal/arxiv annotation. ID: {arxiv_annotation_stub.id}"
            )
            try:
                return get_file_annotation(
                    str(arxiv_annotation_stub.id), mode="pydantic"
                )
            except Exception as err:
                self.set_error(
                    f"Failed to fetch annotation {arxiv_annotation_stub.id}: {err}"
                )
                return None
        return None

    def main(self, strict: bool = False, **kwargs) -> dict | None:
        """Identifies an arXiv PDF.

        - Checks DorsalHub API using the file hash and return its arXiv annotation.
        - If file not indexed to DorsalHub, heuristics try to determine the arXiv ID
        - if arXiv ID found, attempts to retrieve annotation from DorsalHub API using hashed ID
        """
        self.log_debug(f"Identifying {self.file_path} via DorsalHub API...")

        try:
            file_record = identify_file(str(self.file_path), mode="pydantic")
        except NotFoundError:
            file_record = None
        except Exception as err:
            self.set_error(str(err))
            return None

        if file_record:
            arxiv_annotation = self.retrieve_arxiv_annotation(file_record=file_record)
            if arxiv_annotation:
                self.log_debug("Identified arXiv document from file bytes.")
                return arxiv_annotation.record
            elif self.error:
                return None
            else:
                self.log_debug(
                    "File found on DorsalHub, but lacks dorsal/arxiv annotation."
                )
                pass

        elif strict:
            self.set_error(
                f"Strict mode enabled. File record not found on DorsalHub: {self.hash}"
            )
            return None

        self.log_debug(
            "Binary miss/no annotation. Attempting virtual hash heuristics..."
        )

        pdf_title, title_arxiv_id = self.extract_arxiv_id_from_pdf_title()
        if title_arxiv_id:
            self.log_debug(
                f"Inferred arXiv ID from pdf title '{pdf_title}': {title_arxiv_id}"
            )

        filename_arxiv_id = self.extract_arxiv_id_from_file_name()
        if filename_arxiv_id:
            self.log_debug(
                f"Inferred arXiv ID from pdf file name '{self.name}': {filename_arxiv_id}"
            )

        if not (title_arxiv_id or filename_arxiv_id):
            self.set_error(f"Unable to infer arXiv ID for document: {self.file_path}")
            return None

        if title_arxiv_id and filename_arxiv_id:
            if title_arxiv_id != filename_arxiv_id:
                self.set_error(
                    f"Conflicting arXiv IDs found: [{filename_arxiv_id}, {title_arxiv_id}], exiting."
                )
                return None

        arxiv_target_id: str
        if title_arxiv_id:
            arxiv_target_id = title_arxiv_id
        elif filename_arxiv_id:
            arxiv_target_id = filename_arxiv_id
        else:
            return None  # pragma: no cover

        arxiv_title_hash = self._hash_arxiv_id(arxiv_id=arxiv_target_id)

        self.log_debug(f"Querying DorsalHub for virtual hash: {arxiv_title_hash}")
        try:
            virtual_file_record = get_dorsal_file_record(
                hash_string=arxiv_title_hash, mode="pydantic"
            )
        except NotFoundError:
            self.set_error(
                f"Virtual hash for ArXiv ID '{arxiv_target_id}' not found on DorsalHub."
            )
            return None
        except Exception as err:
            self.set_error(str(err))
            return None

        arxiv_annotation = self.retrieve_arxiv_annotation(
            file_record=virtual_file_record
        )
        if arxiv_annotation:
            self.log_debug(
                f"Identified arXiv document from {'title' if title_arxiv_id else 'file name'}."
            )
            return arxiv_annotation.record

        if self.error:
            return None

        self.set_error("Virtual hash found, but lacks dorsal/arxiv annotation.")
        return None
