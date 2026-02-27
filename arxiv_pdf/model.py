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

from importlib.metadata import version

from dorsal import AnnotationModel
from dorsal.api.file import identify_file, get_file_annotation


class ArxivPdf(AnnotationModel):
    id = "github:dorsalhub/dorsal-arxiv"
    version = version("dorsal-arxiv-pdf")

    def main(self, **kwargs) -> dict | None:
        """
        Identify the file against DorsalHub and return its arXiv annotation.
        """
        self.log_debug(f"Identifying {self.file_path} via DorsalHub...")

        try:
            file_record = identify_file(str(self.file_path), mode="pydantic")
        except Exception as e:
            self.set_error(f"Failed to identify file with DorsalHub API: {e}")
            return None

        arxiv_annotation_stub = None
        if file_record.annotations:
            for schema, record in file_record.annotations:
                if schema == "dorsal/arxiv":
                    if record and len(record) > 0:
                        arxiv_annotation_stub = record[0]
                    break

        if not arxiv_annotation_stub:
            self.set_error(
                "No dorsal/arxiv annotation found for this file on DorsalHub."
            )
            return None

        self.log_debug(f"Found arXiv annotation ID: {arxiv_annotation_stub.id}")

        try:
            full_annotation = get_file_annotation(
                str(arxiv_annotation_stub.id), mode="pydantic"
            )
        except Exception as e:
            self.set_error(
                f"Failed to fetch full annotation {arxiv_annotation_stub.id}: {e}"
            )
            return None

        return full_annotation.record
