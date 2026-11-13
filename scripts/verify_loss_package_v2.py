"""Read-only complete ZIP member and SHA-256 verification for the handoff."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile


def verify_zip(path, expected_sha256=None):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(65536):
            digest.update(chunk)
    digest = digest.hexdigest()
    if expected_sha256 is not None and digest != expected_sha256:
        raise ValueError("archive SHA-256 mismatch")
    prefix = "interop-benchmark-20261113/"
    manifest_name = prefix + "release-manifest.json"
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("duplicate ZIP members")
        for name in names:
            normalized = PurePosixPath(name)
            if not name.startswith(prefix) or normalized.is_absolute() or ".." in normalized.parts or "\\" in name:
                raise ValueError("unexpected ZIP member path")
        manifest = json.loads(archive.read(manifest_name))
        files = manifest["files"]
        if len({item["path"] for item in files}) != len(files):
            raise ValueError("duplicate manifest members")
        expected = {prefix + item["path"] for item in files} | {manifest_name}
        if set(names) != expected or len(files) != manifest["total_files"]:
            raise ValueError("ZIP/manifest census mismatch")
        total = 0
        for item in files:
            item_hash, item_bytes = hashlib.sha256(), 0
            with archive.open(prefix + item["path"]) as stream:
                while chunk := stream.read(65536):
                    item_hash.update(chunk)
                    item_bytes += len(chunk)
            if item_bytes != item["bytes"] or item_hash.hexdigest() != item["sha256"]:
                raise ValueError("ZIP payload mismatch: " + item["path"])
            total += item_bytes
        if total != manifest["total_bytes"]:
            raise ValueError("manifest byte total mismatch")
    return {"status": "passed", "archive_sha256": digest, "payload_files_verified": len(files),
            "payload_bytes_verified": total, "scope": "Complete archive integrity; source/evidence semantics are checked by the delivered replay command."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--expected-sha256")
    args = parser.parse_args()
    print(json.dumps(verify_zip(args.zip, args.expected_sha256)))


if __name__ == "__main__":
    main()
