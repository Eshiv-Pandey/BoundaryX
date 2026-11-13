"""Resource failure/missing data must not manufacture measurements or success."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from interoperability import benchmark_resources_v1 as resources


class ResourceTests(unittest.TestCase):
    def test_os_peak_is_positive_or_explicitly_unavailable(self):
        result = resources.process_peak()
        if sys.platform in ("win32", "linux", "darwin"):
            self.assertEqual(result["status"], "observed", result)
            self.assertGreater(result["peak_resident_bytes"], 0)
            self.assertTrue(result["source"])
        with patch.object(sys, "platform", "unsupported-test-platform"):
            result = resources.process_peak()
        self.assertEqual(result["status"], "unavailable")
        self.assertIsNone(result["peak_resident_bytes"])

    def test_empty_and_failed_workers_retain_missing_values(self):
        empty = resources.summarize([])
        self.assertIsNone(empty["peak_resident_bytes"]["maximum"])
        self.assertIsNone(empty["preparation_ns"]["total"])
        reply = {"resources": {"schema_version": resources.SCHEMA,
            "memory": {"status": "observed", "peak_resident_bytes": 4096, "source": "test"},
            "timings": {name: 1 for name in resources.TIMINGS}}}
        summary = resources.summarize([reply, {"status": "timed_out"}, reply])
        self.assertEqual(summary["invocations"], 3)
        self.assertEqual(summary["peak_resident_bytes"],
                         {"samples": [4096, None, 4096], "observed": 2, "missing": 1, "maximum": 4096})
        self.assertEqual(summary["preparation_ns"]["total"], 2)
        invalid = deepcopy(reply)
        invalid["resources"]["memory"]["peak_resident_bytes"] = True
        with self.assertRaises(ValueError):
            resources.summarize([invalid])
        invalid = deepcopy(reply)
        invalid["resources"]["timings"]["preparation_ns"] = -1
        with self.assertRaises(ValueError):
            resources.summarize([invalid])

    def test_imported_function_error_still_records_resources_and_input_integrity(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            job = {"runtime_manifest": {"input": "unchanged"}, "now": 100,
                   "kind": "evaluate", "module": "interoperability.refinement",
                   "entrypoint": "missing_test_entrypoint", "reply_path": str(folder / "reply.json")}
            (folder / "input.json").write_text(json.dumps(job), encoding="utf-8")
            resources.worker(str(folder / "input.json"))
            reply = json.loads((folder / "reply.json").read_bytes())
            self.assertEqual(reply["status"], "error")
            self.assertEqual(reply["error_type"], "AttributeError")
            self.assertTrue(reply["input_unchanged"])
            self.assertNotIn("result", reply)
            self.assertIsNone(reply["resources"]["timings"]["result_serialization_ns"])
            self.assertEqual(resources.summarize([reply])["invocations"], 1)


if __name__ == "__main__":
    unittest.main()
