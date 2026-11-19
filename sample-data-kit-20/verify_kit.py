"""Read-only checks for the generated manual beta-testing package."""

from collections import Counter
from pathlib import Path

from openpyxl import load_workbook
from pypdf import PdfReader

from build_kit import PROJECTS, ROOT, STATUS_SCENARIOS, actual_funding, implementation_status


def verify() -> None:
    assert len(PROJECTS) == 20
    assert Counter(project.priority for project in PROJECTS) == {"High": 10, "Low": 10}
    assert Counter(project.document_condition for project in PROJECTS) == {
        "relevant": 14, "none": 3, "unrelated": 3,
    }
    assert len({project.title for project in PROJECTS}) == 20
    assert set(STATUS_SCENARIOS) == {project.number for project in PROJECTS}
    assert {project.primary for project in PROJECTS} == {"DPWH", "DOH", "DOTr", "DSWD"}
    assert sum({project.primary, *project.collaborators} == {"DPWH", "DOTr"} for project in PROJECTS) >= 4
    assert sum({project.primary, *project.collaborators} == {"DOH", "DSWD"} for project in PROJECTS) >= 4

    forbidden = ("sample project", "fictional project", "fake proposal", "test project")
    pdf_count = 0
    for project in PROJECTS:
        assert sum(amount for _year, amount in project.annual_budgets) == project.total_budget
        assert len(project.annual_budgets) == project.end_year - project.start_year + 1
        assert implementation_status(project) in {
            "New", "Not Implemented", "Ongoing", "Completed", "On Hold", "Cancelled",
        }
        actual = actual_funding(project)
        assert [year for year, _amount in actual] == [year for year, _amount in project.annual_budgets]
        if implementation_status(project) == "Completed":
            assert project.end_year < 2026
            assert sum(amount or 0 for _year, amount in actual) == project.total_budget
        if implementation_status(project) in {"New", "Not Implemented"}:
            assert all(amount is None for _year, amount in actual)
        if project.priority == "High":
            assert project.total_score >= 70 and project.total_budget >= 200_000_000
        else:
            assert project.total_score < 70
        assert len(project.raw_scores) == len(project.criteria)
        assert round(sum(weight * score / 10 for score, (_name, weight) in zip(project.raw_scores, project.criteria)), 2) == project.total_score

        project_file = ROOT / "project-data" / f"project-{project.number:02d}.md"
        scoring_file = ROOT / "scoring-references" / f"project-{project.number:02d}-scoring.md"
        assert project_file.is_file() and scoring_file.is_file()
        text = project_file.read_text(encoding="utf-8").lower()
        assert project.title.lower() in text and implementation_status(project).lower() in text
        assert not any(term in text for term in forbidden)
        for criterion, _weight in project.criteria:
            assert criterion in scoring_file.read_text(encoding="utf-8")

        folder = ROOT / "supporting-documents" / f"project-{project.number:02d}"
        pdfs = list(folder.glob("*.pdf")) if folder.exists() else []
        assert bool(pdfs) == (project.document_condition != "none")
        for pdf in pdfs:
            reader = PdfReader(pdf)
            extracted = " ".join(page.extract_text() or "" for page in reader.pages)
            assert pdf.stat().st_size > 1000 and len(extracted.strip()) > 500
            assert not any(term in extracted.lower() for term in forbidden)
            normalized_text = " ".join(extracted.split())
            if project.document_condition == "relevant":
                assert project.title in normalized_text, str(pdf)
            else:
                assert project.title not in normalized_text, str(pdf)
            pdf_count += 1

    workbook = load_workbook(ROOT / "RDC-NCR_20_Project_Manual_Beta_Testing_Kit.xlsx", read_only=True)
    assert workbook["Project Overview"].max_row == 21
    assert workbook["Contributor Form Entry"].max_row == 21
    assert workbook["Scoring Reference"].max_row == 161
    assert (ROOT / "testing-reference" / "implementation-status-matrix.md").is_file()
    print(f"Verified {len(PROJECTS)} projects, {pdf_count} readable PDFs, 160 criterion rows, and implementation statuses.")


if __name__ == "__main__":
    verify()
