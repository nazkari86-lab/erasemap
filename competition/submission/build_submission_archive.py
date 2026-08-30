# ruff: noqa: E501, I001

from __future__ import annotations

import hashlib
import html
import re
import shutil
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SUBMISSION = ROOT / "competition" / "submission"
ARCHIVE = ROOT / "competition" / "Nurlanuly_Dulat_EraSeMap_Submission.zip"
PACKAGE_ROOT = "Nurlanuly_Dulat_EraSeMap"


FILES: tuple[tuple[Path, str], ...] = (
    (SUBMISSION / "Nurlanuly_Dulat_EraSeMap_Nauchnaya_Rabota_RU.docx", "01_Nauchnaya_Rabota_RU.docx"),
    (SUBMISSION / "Nurlanuly_Dulat_EraSeMap_Nauchnaya_Rabota_RU.pdf", "01_Nauchnaya_Rabota_RU.pdf"),
    (SUBMISSION / "Nurlanuly_Dulat_EraSeMap_Tezisy_RU.docx", "02_Tezisy_RU.docx"),
    (SUBMISSION / "Nurlanuly_Dulat_EraSeMap_Tezisy_RU.pdf", "02_Tezisy_RU.pdf"),
    (SUBMISSION / "Nurlanuly_Dulat_EraSeMap_Annotatsiya_RU_EN.docx", "03_Annotatsiya_RU_EN.docx"),
    (SUBMISSION / "Nurlanuly_Dulat_EraSeMap_Annotatsiya_RU_EN.pdf", "03_Annotatsiya_RU_EN.pdf"),
    (SUBMISSION / "Nurlanuly_Dulat_EraSeMap_Presentation_RU.pptx", "04_Presentation_RU.pptx"),
    (SUBMISSION / "Nurlanuly_Dulat_EraSeMap_Otzyv_Rukovoditelya_DRAFT.docx", "05_Otzyv_Rukovoditelya_DRAFT.docx"),
    (SUBMISSION / "Nurlanuly_Dulat_EraSeMap_Otzyv_Rukovoditelya_DRAFT.pdf", "05_Otzyv_Rukovoditelya_DRAFT.pdf"),
    (SUBMISSION / "Nurlanuly_Dulat_EraSeMap_Registration_Data_DRAFT.docx", "06_Registration_Data_DRAFT.docx"),
    (SUBMISSION / "Nurlanuly_Dulat_EraSeMap_Registration_Data_DRAFT.pdf", "06_Registration_Data_DRAFT.pdf"),
    (SUBMISSION / "README_RU.md", "07_README_RU.md"),
    (SUBMISSION / "SUBMISSION_CHECKLIST_RU.md", "08_SUBMISSION_CHECKLIST_RU.md"),
    (ROOT / "docs" / "JURY_DEFENSE_10_MIN_RU.md", "Defense/JURY_DEFENSE_10_MIN_RU.md"),
    (ROOT / "docs" / "JURY_DEFENSE_RU.md", "Defense/JURY_DEFENSE_RU.md"),
    (ROOT / "docs" / "JUDGE_QA_RU.md", "Defense/JUDGE_QA_RU.md"),
    (ROOT / "outputs" / "synthetic-bank-demo-v1" / "index.html", "Demo/Bank/index.html"),
    (ROOT / "outputs" / "synthetic-bank-demo-v1" / "scenario.json", "Demo/Bank/scenario.json"),
    (ROOT / "outputs" / "synthetic-bank-control-plane-v1" / "index.html", "Demo/Control_Plane_512/index.html"),
    (ROOT / "outputs" / "synthetic-bank-control-plane-v1" / "manifest.json", "Demo/Control_Plane_512/manifest.json"),
    (ROOT / "outputs" / "synthetic-bank-control-plane-v1" / "README.txt", "Demo/Control_Plane_512/README.txt"),
    (ROOT / "outputs" / "jury-showcase-v1" / "index.html", "Demo/Evidence/index.html"),
    (ROOT / "outputs" / "jury-showcase-v1" / "report.json", "Demo/Evidence/report.json"),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspectable_bytes(path: Path) -> bytes:
    if path.suffix.lower() in {".md", ".txt"}:
        return path.read_bytes()
    if path.suffix.lower() not in {".docx", ".pptx"}:
        return b""
    chunks: list[str] = []
    with zipfile.ZipFile(path) as archive:
        for name in sorted(archive.namelist()):
            if not name.endswith(".xml"):
                continue
            xml = archive.read(name).decode("utf-8", errors="ignore")
            chunks.extend(html.unescape(value) for value in re.findall(r"<(?:a:t|w:t)(?:\s[^>]*)?>(.*?)</(?:a:t|w:t)>", xml))
    return "\n".join(chunks).encode("utf-8")


def reject_private_identifiers(path: Path) -> None:
    text = inspectable_bytes(path).decode("utf-8", errors="ignore")
    patterns = {
        "possible 12-digit identifier": r"(?<!\d)\d{12}(?!\d)",
        "possible Kazakhstan phone": r"(?:\+7|8)[\s()\-]*7\d{2}[\s()\-]*\d{3}",
    }
    for label, pattern in patterns.items():
        if re.search(pattern, text):
            raise ValueError(f"{label} found in public package file: {path}")


def build() -> Path:
    missing = [source for source, _ in FILES if not source.is_file()]
    if missing:
        raise FileNotFoundError("Missing package inputs: " + ", ".join(map(str, missing)))

    with tempfile.TemporaryDirectory(prefix="erasemap-submission-") as temp:
        stage = Path(temp) / PACKAGE_ROOT
        for source, destination in FILES:
            target = stage / destination
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            reject_private_identifiers(target)

        checksum_lines = [
            f"{sha256(path)}  {path.relative_to(stage).as_posix()}"
            for path in sorted(stage.rglob("*"))
            if path.is_file()
        ]
        (stage / "SHA256SUMS.txt").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")

        if ARCHIVE.exists():
            ARCHIVE.unlink()
        with zipfile.ZipFile(ARCHIVE, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for path in sorted(stage.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(stage.parent).as_posix())

    return ARCHIVE


if __name__ == "__main__":
    result = build()
    print(f"{result}  sha256={sha256(result)}")
