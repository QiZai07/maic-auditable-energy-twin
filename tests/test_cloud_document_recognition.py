from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))

from src.cloud_document_recognition import recognise_document  # noqa: E402


class TestCloudDocumentRecognition(unittest.TestCase):
    def test_pdf_request_is_stateless_and_structured(self) -> None:
        expected = {"document_type": "bill", "summary": "One electricity bill", "facts": [], "equipment": [], "review_items": []}

        def fake_transport(payload, headers):
            self.assertFalse(payload["store"])
            self.assertEqual(payload["text"]["format"]["type"], "json_schema")
            self.assertEqual(payload["input"][0]["content"][1]["type"], "input_file")
            self.assertTrue(headers["Authorization"].startswith("Bearer "))
            return {"id": "resp_test", "output_text": json.dumps(expected)}

        result = recognise_document("bill.pdf", b"%PDF-1.7\n%%EOF", "test-key", transport=fake_transport)
        self.assertEqual(result["document_type"], "bill")
        self.assertEqual(result["retention"], "store:false")

    def test_unsupported_content_is_rejected_before_transport(self) -> None:
        with self.assertRaisesRegex(ValueError, "limited to PDF and image"):
            recognise_document("data.csv", b"a,b\n1,2", "test-key")


if __name__ == "__main__":
    unittest.main(verbosity=2)
