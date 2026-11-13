"""Differential byte and publication controls for the delivery-only IO adapter."""
import json
from pathlib import Path
import tempfile
import unittest
from scripts import loss_json_io_v2 as streaming
from scripts import run_loss_benchmark_v1 as frozen


class StreamingOutputControls(unittest.TestCase):
    def compare(self, value):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.json"
            streaming.write_new(output, value)
            self.assertEqual(output.read_bytes(), frozen.canonical(value) + b"\n")

    def test_unicode_and_escaping_match_frozen_bytes(self):
        self.compare({"unicode": "हस्तांतरण / café \u2028", "escape": '"\\\n\t\r', "empty": ""})

    def test_json_types_empty_values_and_duplicates_match(self):
        self.compare({"types": [True, 1, 1.0, False, None, -0.0], "empty": [{}, []], "records": [{"id": 1}, {"id": 1}]})

    def test_nested_order_and_array_order_match(self):
        self.compare({"z": [{"b": 2, "a": [3, 1]}, {"nested": {"z": 0, "a": 9}}], "a": 5})

    def test_existing_output_is_not_changed(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.json"
            output.write_bytes(b"preserved")
            with self.assertRaises(FileExistsError):
                streaming.write_new(output, {"new": True})
            self.assertEqual(output.read_bytes(), b"preserved")

    def test_nonfinite_output_is_rejected(self):
        for value in (float("nan"), float("inf"), float("-inf")):
            with tempfile.TemporaryDirectory() as directory:
                with self.assertRaises(ValueError):
                    streaming.write_new(Path(directory) / "bad.json", {"value": value})
                with self.assertRaises(ValueError):
                    frozen.canonical({"value": value})
