"""Render the manual to PDF.

The source of truth is `manual-cyrvanta.html`, which is written as artifact
content -- a `<title>`, a `<style>` and the body, with no document skeleton --
so the same file can be published as an Artifact and printed here. This wraps
it in a document and prints it through headless Chrome, which is the only
renderer on hand that supports the grid, flexbox and web fonts the page uses.

Usage:  python docs/manual/build-pdf.py
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "docs" / "manual" / "manual-cyrvanta.html"
OUTPUT = ROOT / "manual_cyrvanta_v2_master.pdf"

CHROME_CANDIDATES = [
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    Path("/usr/bin/google-chrome"),
    Path("/usr/bin/chromium"),
]


def find_browser() -> Path:
    for candidate in CHROME_CANDIDATES:
        if candidate.exists():
            return candidate
    found = shutil.which("google-chrome") or shutil.which("chromium")
    if found:
        return Path(found)
    raise SystemExit("No Chrome or Edge found; cannot render the PDF.")


def main() -> None:
    browser = find_browser()
    body = SOURCE.read_text(encoding="utf-8")
    document = (
        "<!doctype html>\n"
        '<html lang="es">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"{body}\n</body>\n</html>\n"
    ).replace("<title>", "<title>", 1)
    # The source has no <body>; open it right after the head content so the
    # closing tag above matches.
    document = document.replace("</style>\n", "</style>\n</head>\n<body>\n", 1)

    with tempfile.TemporaryDirectory() as workspace:
        staged = Path(workspace) / "manual.html"
        staged.write_text(document, encoding="utf-8")
        profile = Path(workspace) / "profile"
        subprocess.run(
            [
                str(browser),
                "--headless=new",
                "--disable-gpu",
                "--no-first-run",
                "--no-pdf-header-footer",
                f"--user-data-dir={profile}",
                # Web fonts need the network; without it the page silently
                # falls back and the PDF looks nothing like the artifact.
                "--virtual-time-budget=20000",
                f"--print-to-pdf={OUTPUT}",
                staged.as_uri(),
            ],
            check=True,
            capture_output=True,
            timeout=180,
        )

    if not OUTPUT.exists():
        raise SystemExit("Chrome reported success but wrote no file.")
    print(f"{OUTPUT.name}  ({OUTPUT.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    sys.exit(main())
