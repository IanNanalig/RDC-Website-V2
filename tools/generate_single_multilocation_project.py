"""Build one fictional manual-entry project kit without changing the database."""

from datetime import date
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1] / "sample-project-kit-multi-location"
DOCS = ROOT / "supporting-documents"
TITLE = "Metro Manila Safe School Access Corridor Program"
AGENCY = "Department of Public Works and Highways (DPWH)"
COLLABORATING_AGENCY = "Department of Transportation (DOTr)"
MARK = "SAMPLE DOCUMENT - FOR BETA TESTING ONLY"
DOC_DATE = date(2026, 11, 9).strftime("%B %d, %Y")

FIELDS = [
    ("Agency Name", "DPWH"),
    ("Collaborating Agencies", "Department of Transportation (DOTr)"),
    ("Program", "NCR Safe School Mobility and Road Safety Program"),
    ("Project/Activity", TITLE),
    ("Location", "Manila; Pasay; Quezon City (select all three)"),
    ("Description", "Fictional proposal to improve walking routes near selected public schools in Manila, Pasay, and Quezon City. Works include raised crossings, accessible curb ramps, repaired sidewalks, protected waiting areas, drainage at pedestrian approaches, and safer connections to public transport stops. DPWH is the primary agency; DOTr supports transport-stop coordination and traffic-safety review."),
    ("Objective", "Reduce pedestrian conflicts on school approaches, provide continuous accessible paths, and improve safe transfers between schools and public transport in three Metro Manila cities."),
    ("Start Year", "2027"),
    ("End Year", "2029"),
    ("Funding Requirement 2027 (PHP)", 50_000_000),
    ("Funding Requirement 2028 (PHP)", 60_000_000),
    ("Funding Requirement 2029 (PHP)", 40_000_000),
    ("Funding Requirement Total (PHP)", 150_000_000),
    ("Actual/Approved Funding (PHP)", "Leave blank: proposal is not yet implemented or approved."),
    ("Funding Source", "Agency"),
    ("UACS Code (if GAA-funded)", "Not shown for the selected Funding Source."),
    ("PIP Included", "Yes"),
    ("ARNIPAP Included", "No"),
    ("LUDIP (for SUCs)", "Not Applicable"),
    ("IFPs Included", "Yes"),
    ("Part of the Convergence Program (PCB)", "No"),
    ("Convergence Program (PCB)", "Not shown when PCB is No."),
    ("RDC-NCR Endorsed", "No"),
    ("RDC-NCR Development Sector", "Sectoral Committee on Infrastructure Development (SCID)"),
    ("RDP-NCR Main Chapter", "13 Expand and Upgrade Infrastructure Infrastructure"),
    ("Status", "New"),
    ("Sustainable Development Goals", "9 - Industry, innovation and infrastructure; 11 - Sustainable cities and communities"),
    ("Physical Accomplishment", "Not shown for New status; no accomplishment is claimed."),
    ("Financial Accomplishment", "Not shown for New status; no accomplishment is claimed."),
    ("Remarks", "Not shown for New status."),
]

VALIDATOR_INPUTS = [
    ("Readiness Level", "With concept paper/none", "The kit has a concept note, preliminary estimate, and plan, but no completed feasibility study or detailed design. Beta-test classification only."),
    ("GAD Responsiveness", "Promising GAD prospects", "Accessible routes could benefit different user groups; this is a provisional test choice, not a completed GAD assessment."),
    ("Spatial Coverage", "Specific LGUs", "The sample names Manila, Pasay, and Quezon City; it does not claim region-wide coverage."),
    ("SCEED Track (if applicable)", "Not shown", "The selected sector is SCID, so do not enter an SCEED track."),
    ("Estimated Beneficiaries", "75,000", "Fictional planning estimate for beta testing; no verified count is claimed."),
    ("Contributed RDP Outcomes", "2", "Provisional example for testing the input control; the Validator must verify against the actual RDP outcomes before a real decision."),
    ("Regional Spatial Category", "Leave blank", "The sample is below the current PHP 200 million regional cutoff, so this regional input is not required. None of the regional options accurately describes three cities."),
    ("Readiness Evidence Notes", "Concept note, preliminary cost estimate, and implementation plan attached. No feasibility study, detailed engineering, approved funding, or verified baseline is claimed.", "Use only if the uploaded PDFs match the project and the Validator agrees with this summary."),
]

DOCUMENTS = [
    (
        "01_Project_Concept_Note.pdf",
        "Project Concept Note",
        "Purpose and proposed scope",
        [
            "The proposed program would establish safer walking routes on selected school approaches in Manila, Pasay, and Quezon City. The sites are examples for beta testing and are not approved locations.",
            "The scope covers raised pedestrian crossings, continuous sidewalks, tactile and accessible curb ramps, protected waiting areas, street lighting improvements where needed, and drainage repairs where surface water affects pedestrian access.",
            "DPWH would lead road and sidewalk works. DOTr would coordinate the interfaces with nearby public transport stops and advise on safe transfer points. City governments and school communities would be consulted during detailed design; this sample document records no actual consultation or approval.",
            "Expected outputs: three city-level corridor packages, a preliminary accessibility checklist for each package, and a monitoring baseline for pedestrian access and observed conflicts. Intended beneficiaries include students, caregivers, pedestrians with disabilities, and transit users near the proposed corridors.",
        ],
    ),
    (
        "02_Preliminary_Cost_Estimate.pdf",
        "Preliminary Cost Estimate",
        "Illustrative budget for beta testing",
        [
            "The PHP 150 million requirement is a planning example only. It is neither an appropriation nor an approved cost estimate. The three annual allocations are PHP 50 million in 2027, PHP 60 million in 2028, and PHP 40 million in 2029.",
            "Indicative work packages (PHP million): sidewalks and accessible ramps 48; raised crossings and traffic calming 35; waiting-area and transport-stop access 20; drainage and surface repairs 17; lighting and safety equipment 10; design, supervision, and contingency 20. Total: 150.",
            "The allocation would be refined after site surveys, utility checks, drainage review, accessibility audit, and procurement planning. No quantity survey, contract award, or funding commitment is represented by this sample.",
        ],
    ),
    (
        "03_Implementation_and_Monitoring_Plan.pdf",
        "Implementation and Monitoring Plan",
        "Proposed sequence and evaluation measures",
        [
            "2027: undertake site screening and accessibility walks for candidate school corridors in Manila, Pasay, and Quezon City; prepare concept designs and baseline measures; begin a first construction package where permissions and designs are complete.",
            "2028: deliver the main sidewalk, crossing, and transport-stop interface works in staged packages. Maintain temporary pedestrian access during construction and document any changes to the proposed corridor limits.",
            "2029: complete remaining packages, inspect accessibility and drainage performance, correct defects, and establish maintenance responsibilities with relevant road and local authorities.",
            "Illustrative measures: number of corridor packages completed; length of continuous accessible sidewalk; number of upgraded crossings and curb ramps; documented safe routes to nearby transport stops; and post-work observations of pedestrian conflicts. Baselines and targets must be verified before real implementation.",
        ],
    ),
]


def pdf_file(path, heading, subtitle, paragraphs):
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Marker", parent=styles["Normal"], textColor=colors.HexColor("#9c1c24"), fontName="Helvetica-Bold", alignment=TA_CENTER, fontSize=10, spaceAfter=12))
    styles["BodyText"].leading = 15
    styles["BodyText"].spaceAfter = 10
    story = [Paragraph(MARK, styles["Marker"]), Paragraph(heading, styles["Title"]), Spacer(1, 10)]
    metadata = [
        ["Project", TITLE], ["Originating agency", AGENCY],
        ["Collaborating agency", COLLABORATING_AGENCY],
        ["Date", DOC_DATE], ["Coverage", "Manila, Pasay, and Quezon City"],
        ["Document purpose", subtitle],
    ]
    table = Table(metadata, colWidths=[1.55 * inch, 5.0 * inch])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eaf2fc")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("LINEBELOW", (0, -1), (-1, -1), 0.5, colors.HexColor("#9bb8db")),
    ]))
    story.extend([table, Spacer(1, 15)])
    for paragraph in paragraphs:
        story.append(Paragraph(paragraph, styles["BodyText"]))
    doc = SimpleDocTemplate(str(path), pagesize=(8.27 * inch, 11.69 * inch), topMargin=0.58 * inch, bottomMargin=0.58 * inch)
    doc.build(story)


def spreadsheet(path):
    wb = Workbook()
    ws = wb.active
    ws.title = "Contributor Form"
    ws.append(["FICTIONAL SAMPLE PROJECT - FOR BETA TESTING ONLY", ""])
    ws.append(["Field in current Contributor Form", "Value to enter"])
    for label, value in FIELDS:
        ws.append([label, value])
    ws.freeze_panes = "B3"
    ws.column_dimensions["A"].width = 39
    ws.column_dimensions["B"].width = 105
    for row in ws:
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[row[0].row].height = 32 if row[0].row > 2 else 25
    for cell in ws[1] + ws[2]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="174A85")
    for row in range(3, ws.max_row + 1):
        if isinstance(ws.cell(row, 2).value, int):
            ws.cell(row, 2).number_format = '#,##0'
    notes = wb.create_sheet("Documents and Use")
    notes.append(["Document", "What it contains", "Upload instruction"])
    for filename, heading, subtitle, _ in DOCUMENTS:
        notes.append([filename, f"{heading}: {subtitle}", "Upload to this project as a separate supporting document."])
    notes.append(["Workflow", "Save a draft, upload all three PDFs, then submit for validation.", "No database records are created by this kit."])
    notes.append(["Validation", "Validator facts, AI results, and priority confirmation must be entered through the real review workflow.", "Do not treat this sample as approved or funded."])
    for col, width in {"A": 51, "B": 90, "C": 72}.items():
        notes.column_dimensions[col].width = width
    for row in notes:
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    for cell in notes[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="174A85")
    validator = wb.create_sheet("Validator Inputs")
    validator.append(["VALIDATOR-ONLY BETA TEST INPUTS", "", ""])
    validator.append(["Field in Validator Facts Supplement", "Suggested test entry", "Basis and limits"])
    for row in VALIDATOR_INPUTS:
        validator.append(list(row))
    validator.append(["Priority confirmation", "Do not prefill", "Run the actual AI scorer, review its evidence, and make any human decision through the live Validator workflow."])
    for col, width in {"A": 39, "B": 92, "C": 107}.items():
        validator.column_dimensions[col].width = width
    validator.freeze_panes = "B3"
    for row in validator:
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
        validator.row_dimensions[row[0].row].height = 48 if row[0].row > 2 else 25
    for cell in validator[1] + validator[2]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="174A85")
    wb.save(path)


def main():
    DOCS.mkdir(parents=True, exist_ok=True)
    spreadsheet(ROOT / "Project_Manual_Entry.xlsx")
    for filename, heading, subtitle, paragraphs in DOCUMENTS:
        pdf_file(DOCS / filename, heading, subtitle, paragraphs)
    (ROOT / "README.txt").write_text(
        "FICTIONAL SAMPLE PROJECT - FOR BETA TESTING ONLY\n\n"
        f"Project: {TITLE}\nPrimary agency: DPWH\nCollaborator: DOTr\n"
        "Locations: Manila, Pasay, Quezon City\nStatus: New\n\n"
        "Use Project_Manual_Entry.xlsx to enter the project manually. Upload all three separate PDFs "
        "from supporting-documents. Save a draft before uploading, then submit for validation. "
        "Validator-only suggestions are on the Validator Inputs tab. They are provisional test values; "
        "the Validator must inspect the actual project and documents before using them. "
        "No project, account, AI analysis, or approval has been inserted into the database.\n",
        encoding="utf-8",
    )
    wb = load_workbook(ROOT / "Project_Manual_Entry.xlsx", read_only=True)
    assert wb["Contributor Form"].max_row == len(FIELDS) + 2
    assert sum(value for label, value in FIELDS if label.startswith("Funding Requirement 20")) == 150_000_000
    assert wb["Validator Inputs"].max_row == len(VALIDATOR_INPUTS) + 3
    for filename, _, _, _ in DOCUMENTS:
        path = DOCS / filename
        reader = PdfReader(str(path))
        extracted = " ".join(page.extract_text() or "" for page in reader.pages)
        assert len(extracted) > 500 and MARK in extracted and TITLE in extracted
        assert path.stat().st_size > 2_000
    zip_path = ROOT.parent / "RDC-NCR_One_Multi-Location_Project_Kit.zip"
    with ZipFile(zip_path, "w", ZIP_DEFLATED) as archive:
        for path in ROOT.rglob("*"):
            if path.is_file():
                archive.write(path, f"{ROOT.name}/{path.relative_to(ROOT).as_posix()}")
    print(f"Created {zip_path} ({zip_path.stat().st_size:,} bytes), 1 XLSX and {len(DOCUMENTS)} validated PDFs")


if __name__ == "__main__":
    main()
