"""Copy verified headless browser captures into the report with provenance."""
from pathlib import Path
import hashlib
import json
from PIL import Image, PngImagePlugin

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "reports/supervisor-20261113"


def main():
    validation = DEST / "ui-validation"
    validation.mkdir(parents=True, exist_ok=True)
    source_files = [ROOT / "demo/benchmark-v2" / name for name in ("index.html", "styles.css", "app.js", "data.js")]
    sources = [{"path": p.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in source_files]
    for device in ("desktop", "mobile"):
        original = ROOT / ".impeccable/review" / (device + ".png")
        captured = validation / ("original-" + device + ".png")
        captured.write_bytes(original.read_bytes())
        provenance = {"origin": "Headless Chrome capture of the local benchmark evidence explorer", "generator": "scripts/archive_loss_explorer_review_v2.py",
                      "capture_path": captured.relative_to(ROOT).as_posix(), "capture_sha256": hashlib.sha256(original.read_bytes()).hexdigest(),
                      "sources": sources, "note": "Saved-evidence UI; constructed development tasks and AI-assisted gold explicitly labelled. No generated illustration or model inference."}
        metadata = PngImagePlugin.PngInfo()
        metadata.add_text("Provenance", json.dumps(provenance))
        with Image.open(original) as image:
            image.save(DEST / "images" / ("explorer-" + device + ".png"), pnginfo=metadata)
        (DEST / "images" / ("explorer-" + device + ".provenance.json")).write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    for name in ("browser-check.json", "fix-check.json", "finish-review.md", "finish-verdict.md"):
        original = ROOT / ".impeccable/review" / name
        if original.exists():
            (validation / name).write_bytes(original.read_bytes())


if __name__ == "__main__":
    main()
