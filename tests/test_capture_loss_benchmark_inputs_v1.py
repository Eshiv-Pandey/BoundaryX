"""Tiny authored exporter fixtures; not historical retained evidence."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import capture_loss_benchmark_inputs_v1 as exporter


class PortableInputControls(unittest.TestCase):
    def fixture(self, base):
        root = base / "original"
        raw_files = {"runs/test-fixture/raw.bin": b"\x00\xff\r\nexact bytes\n", "sources/LICENSE.txt": b"Authored test license notice\r\n"}
        for relative, raw in raw_files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        manifest = {"schema_version": exporter.MANIFEST_SCHEMA,
                    "source_files": [{"path": path, "sha256": exporter.identity(raw)["sha256"]} for path, raw in raw_files.items()]}
        manifest_path = base / "manifest.json"
        manifest_path.write_bytes(exporter.canonical(manifest) + b"\n")
        return root, manifest_path, manifest, raw_files

    def test_exact_binary_license_bytes_and_inventory_manifest_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root, manifest_path, _, files = self.fixture(base)
            before = manifest_path.read_bytes()
            output = base / "portable"
            inventory = exporter.capture(root, manifest_path, output)
            self.assertEqual(inventory["unique_file_count"], 2)
            self.assertEqual(inventory["file_total_bytes"], sum(map(len, files.values())))
            self.assertEqual(inventory["source_manifest"]["sha256"], exporter.identity(before)["sha256"])
            for record in inventory["files"]:
                copied = (output / record["path"]).read_bytes()
                self.assertEqual(copied, files[record["path"]])
                self.assertEqual(exporter.identity(copied), {key: record[key] for key in ("sha256", "bytes")})
            self.assertEqual(manifest_path.read_bytes(), before)
            self.assertFalse(inventory["service_execution"])
            self.assertEqual(len([p for p in output.rglob("*") if p.is_file()]), 3)

    def test_corrupt_source_and_wrong_pin_hash_fail_before_allocation(self):
        for corrupt_source in (True, False):
            with tempfile.TemporaryDirectory() as temp:
                base = Path(temp)
                root, manifest_path, manifest, _ = self.fixture(base)
                if corrupt_source:
                    (root / manifest["source_files"][-1]["path"]).write_bytes(b"changed source")
                else:
                    manifest["source_files"][-1]["sha256"] = "0" * 64
                    manifest_path.write_bytes(exporter.canonical(manifest))
                output = base / "portable"
                with self.assertRaisesRegex(ValueError, "hash mismatch"):
                    exporter.capture(root, manifest_path, output)
                self.assertFalse(output.exists(), "all pins must verify before any mirror allocation")

    def test_existing_output_empty_or_populated_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root, manifest_path, _, _ = self.fixture(base)
            output = base / "portable"
            output.mkdir()
            with self.assertRaises(FileExistsError):
                exporter.capture(root, manifest_path, output)
            sentinel = output / "keep.bin"
            sentinel.write_bytes(b"untouched")
            with self.assertRaises(FileExistsError):
                exporter.capture(root, manifest_path, output)
            self.assertEqual(sentinel.read_bytes(), b"untouched")

    def test_escaping_windows_alias_sensitive_and_private_paths_rejected(self):
        invalid = ("../outside.json", "runs/../../outside.json", "/absolute.json", "C:/outside.json", "C:relative.json", "\\\\server\\share\\file", "runs\\file.json", "runs//file.json", "runs/./file.json", "runs/file.json:stream", "runs/file.json.", "runs/CON.txt", "runs/CONIN$", "runs/CONOUT$.txt", "runs/COM\u00b9.txt", "runs/LPT\u00b2.txt", "runs/bad?.json", "runs/bad*.json", "runs/bad|.json", "runs/bad<.json", "runs/inner\nline.json", "runs/.env", "runs/.env.production", ".codex/CONTRIBUTION_RULES.md", "docs/AGENTS.md", "USER_INSTRUCTIONS.md", "credentials.json", ".aws/credentials", "keys/id_rsa", "inventory.json")
        for path in invalid:
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    exporter.validate_relative(path)
        self.assertEqual(exporter.validate_relative("runs/case/private-native-http.jsonl"), Path("runs/case/private-native-http.jsonl"))

    def test_unsafe_pin_duplicate_and_missing_file_fail_without_output(self):
        changes = (lambda m: m["source_files"][0].update(path="../outside"),
                   lambda m: m["source_files"].append(deepcopy(m["source_files"][0])),
                   lambda m: m["source_files"][0].update(path="runs/missing.bin"),
                   lambda m: m["source_files"][0].update(sha256="not-a-hash"),
                   lambda m: m["source_files"][0].update(bytes=1))
        for change in changes:
            with tempfile.TemporaryDirectory() as temp:
                base = Path(temp)
                root, manifest_path, manifest, _ = self.fixture(base)
                change(manifest)
                manifest_path.write_bytes(exporter.canonical(manifest))
                output = base / "portable"
                with self.assertRaises(ValueError):
                    exporter.capture(root, manifest_path, output)
                self.assertFalse(output.exists())

    def test_source_and_output_symlink_escape_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root, manifest_path, manifest, files = self.fixture(base)
            outside = base / "outside"
            outside.mkdir()
            (outside / "raw.bin").write_bytes(files["runs/test-fixture/raw.bin"])
            source = root / "runs/test-fixture/raw.bin"
            source.unlink()
            try:
                source.symlink_to(outside / "raw.bin")
                (base / "output-link").symlink_to(outside, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation unavailable in this test environment")
            with self.assertRaisesRegex(ValueError, "symlink|junction"):
                exporter.capture(root, manifest_path, base / "portable")
            self.assertFalse((base / "portable").exists())
            with self.assertRaisesRegex(ValueError, "symlink|junction"):
                exporter.prepare_output(base / "output-link/mirror")
            self.assertFalse((outside / "mirror").exists())

    def test_link_or_junction_detection_branches_require_no_link_privilege(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp).resolve()
            root = base / "original"
            root.mkdir()
            linked = root / "runs"
            with patch.object(exporter, "is_link", side_effect=lambda path: path == linked):
                with self.assertRaisesRegex(ValueError, "symlink|junction"):
                    exporter.no_links_below(root, linked / "file.bin")
            linked_output_parent = base / "linked-output"
            with patch.object(exporter, "is_link", side_effect=lambda path: path == linked_output_parent):
                with self.assertRaisesRegex(ValueError, "symlink|junction"):
                    exporter.prepare_output(linked_output_parent / "mirror")

    def test_source_and_manifest_ancestor_links_fail_before_allocation(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp).resolve()
            root, manifest_path, _, _ = self.fixture(base)
            with patch.object(exporter, "is_link", side_effect=lambda path: path == root.parent):
                with self.assertRaisesRegex(ValueError, "symlink|junction"):
                    exporter.capture(root, manifest_path, base / "portable")
            manifest_dir = base / "manifest-directory"
            manifest_dir.mkdir()
            relocated = manifest_dir / "manifest.json"
            relocated.write_bytes(manifest_path.read_bytes())
            with patch.object(exporter, "is_link", side_effect=lambda path: path == manifest_dir):
                with self.assertRaisesRegex(ValueError, "symlink|junction"):
                    exporter.capture(root, relocated, base / "portable")
            self.assertFalse((base / "portable").exists())

    def test_duplicate_manifest_json_keys_cannot_override_bad_values(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root, manifest_path, manifest, _ = self.fixture(base)
            duplicate = exporter.canonical(manifest).decode("utf-8")[:-1] + ',"schema_version":"' + exporter.MANIFEST_SCHEMA + '"}'
            manifest_path.write_text(duplicate, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate manifest JSON key"):
                exporter.capture(root, manifest_path, base / "portable")
            self.assertFalse((base / "portable").exists())

    def test_cli_roundtrip_and_refusal_do_not_execute_fixture_sources(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root, manifest_path, _, files = self.fixture(base)
            output = base / "portable"
            command = [sys.executable, "-B", str(ROOT / "scripts/capture_loss_benchmark_inputs_v1.py"), "--root", str(root), "--manifest", str(manifest_path), "--output", str(output)]
            completed = subprocess.run(command, capture_output=True, text=True, timeout=20)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            receipt = json.loads(completed.stdout)
            self.assertEqual(receipt["unique_file_count"], len(files))
            repeated = subprocess.run(command, capture_output=True, text=True, timeout=20)
            self.assertNotEqual(repeated.returncode, 0)
            self.assertIn("FileExistsError", repeated.stderr)


if __name__ == "__main__":
    unittest.main()
