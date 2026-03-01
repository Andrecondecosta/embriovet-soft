import re
from pathlib import Path


PATTERNS = [
    r"st\.button\(\"",
    r"st\.success\(\"",
    r"st\.error\(\"",
    r"st\.warning\(\"",
    r"st\.info\(\"",
    r"st\.markdown\(\"",
    r"st\.header\(\"",
    r"st\.subheader\(\"",
    r"st\.caption\(\"",
    r"st\.selectbox\(\"",
    r"st\.radio\(\"",
    r"st\.checkbox\(\"",
    r"st\.text_input\(\"",
    r"st\.date_input\(\"",
    r"st\.number_input\(\"",
    r"st\.file_uploader\(\"",
    r"st\.download_button\(\"",
    r"st\.form_submit_button\(\"",
]


def audit(root: str = "/app"):
    regexes = [re.compile(p) for p in PATTERNS]
    findings = []
    for path in Path(root).rglob("*.py"):
        if path.name.endswith(".bak"):
            continue
        for idx, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if "t(" in line:
                continue
            if any(r.search(line) for r in regexes):
                findings.append((str(path), idx, line.strip()))

    for f in findings:
        print(f"{f[0]}:{f[1]}: {f[2]}")


if __name__ == "__main__":
    audit()