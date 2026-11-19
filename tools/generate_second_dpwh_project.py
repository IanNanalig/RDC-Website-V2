"""Create a distinct fictional DPWH project kit for manual beta testing."""

from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from openpyxl import load_workbook
from pypdf import PdfReader

import generate_single_multilocation_project as kit


kit.ROOT = Path(__file__).resolve().parents[1] / "sample-project-kit-dpwh-overpass"
kit.DOCS = kit.ROOT / "supporting-documents"
kit.TITLE = "South Metro Overpass Joint and Bearing Rehabilitation Program"
kit.COLLABORATING_AGENCY = "None"

changes = {
    "Collaborating Agencies": "Leave blank: DPWH is the sole originating agency in this sample.",
    "Program": "South Metro Road Structure Preservation Program",
    "Project/Activity": kit.TITLE,
    "Location": "Pasay; Parañaque; Muntinlupa (select all three)",
    "Description": "Fictional proposal to assess and rehabilitate selected road overpass expansion joints, bearings, drainage outlets, and approach slabs in Pasay, Parañaque, and Muntinlupa. Work would be staged to preserve traffic access. Candidate structures are illustrative and require engineering inspection before any real selection or design.",
    "Objective": "Improve structural serviceability and road safety at selected overpasses, reduce water-related deterioration, and limit unplanned closures during heavy rain and routine maintenance.",
    "Funding Requirement 2027 (PHP)": 45_000_000,
    "Funding Requirement 2028 (PHP)": 70_000_000,
    "Funding Requirement 2029 (PHP)": 45_000_000,
    "Funding Requirement Total (PHP)": 160_000_000,
    "PIP Included": "No",
    "IFPs Included": "No",
    "Sustainable Development Goals": "9 - Industry, innovation and infrastructure; 11 - Sustainable cities and communities",
}
kit.FIELDS = [(label, changes.get(label, value)) for label, value in kit.FIELDS]

kit.VALIDATOR_INPUTS = [
    ("Readiness Level", "With concept paper/none", "This kit contains a concept note and survey plan, but no completed structural inspection, feasibility study, or detailed engineering design."),
    ("GAD Responsiveness", "Promising GAD prospects", "The sample discusses safer travel for different road users; a real GAD review remains necessary."),
    ("Spatial Coverage", "Specific LGUs", "The proposal names Pasay, Parañaque, and Muntinlupa, not all of NCR."),
    ("SCEED Track (if applicable)", "Not shown", "The selected sector is SCID, so the SCEED-only field does not apply."),
    ("Estimated Beneficiaries", "90,000", "Fictional planning estimate for testing the field; no traffic count is verified."),
    ("Contributed RDP Outcomes", "1", "Provisional test entry; compare it with the actual RDP outcome definitions before a real review."),
    ("Regional Spatial Category", "Leave blank", "At PHP 160 million the proposal is below the current PHP 200 million regional cutoff. None of the regional choices accurately describes three cities."),
    ("Readiness Evidence Notes", "Concept note, proposed structural survey plan, and preliminary cost and staging outline attached. No site inspection, certified condition rating, approved budget, or engineering design is claimed.", "Use only after confirming the three files match the project."),
]

kit.DOCUMENTS = [
    (
        "01_Overpass_Project_Concept_Note.pdf",
        "Project Concept Note",
        "Proposed overpass preservation scope",
        [
            "This fictional DPWH proposal would evaluate and rehabilitate selected road overpass joints and bearings in Pasay, Parañaque, and Muntinlupa. No structure is represented as having been inspected, approved, or selected for construction.",
            "The proposed scope covers condition screening, replacement or repair of failed expansion joints where confirmed, bearing maintenance or replacement where engineering review supports it, drainage outlet cleaning and repair, and approach-slab treatment at confirmed defects.",
            "DPWH would lead engineering, procurement, and construction. Traffic management plans and temporary access would be prepared before site work. Any coordination with local road and traffic authorities would occur through the real project process; this beta-test file records no actual agreement.",
            "Expected outputs are condition-based work packages for up to three city areas, documented treatment decisions for inspected structures, and post-work checks for water ingress, ride quality, and safe traffic operations.",
        ],
    ),
    (
        "02_Proposed_Structural_Survey_Plan.pdf",
        "Proposed Structural Survey Plan",
        "Inspection method before final design",
        [
            "The first stage would inventory candidate road overpasses and collect drawings, maintenance records, traffic constraints, and drainage observations. Existing records would be checked against site measurements; this sample does not assert that such records are available.",
            "Qualified engineers would inspect visible joints, bearing seats, approach slabs, deck drainage, and signs of leakage or settlement. Any inaccessible component would be listed as a gap rather than treated as sound. Testing or intrusive investigation would require a separate approved method statement.",
            "Each candidate would receive an inspection sheet with photographs, defect location, observed severity, traffic restrictions, and a recommended next step. Only confirmed defects would advance to detailed design and cost refinement.",
            "The survey output would support a safe work sequence and a decision on whether rehabilitation, replacement, or continued monitoring is appropriate. No inspection result or structural safety rating is fabricated in this document.",
        ],
    ),
    (
        "03_Preliminary_Cost_and_Staging_Outline.pdf",
        "Preliminary Cost and Staging Outline",
        "Illustrative funding and schedule",
        [
            "The planning requirement is PHP 160 million: PHP 45 million for 2027, PHP 70 million for 2028, and PHP 45 million for 2029. These figures are fictional beta-test inputs, not an appropriation, contract value, or approved estimate.",
            "Indicative cost groups in PHP million are: inspection and design 18; expansion-joint treatment 45; bearing and seat works 38; drainage and approach-slab repairs 28; traffic management 12; supervision and contingency 19. Total: 160.",
            "2027 would focus on inventory, inspection, design, and a first confirmed work package. 2028 would carry the main rehabilitation packages using staged closures or off-peak work as designed. 2029 would finish remaining confirmed works, defects correction, and post-work monitoring.",
            "Final quantities, safety controls, traffic staging, and costs depend on actual engineering findings. A structure with no confirmed defect would not receive work solely because it appears in this illustrative program.",
        ],
    ),
]


def main():
    kit.DOCS.mkdir(parents=True, exist_ok=True)
    kit.spreadsheet(kit.ROOT / "Project_Manual_Entry.xlsx")
    for filename, heading, subtitle, paragraphs in kit.DOCUMENTS:
        kit.pdf_file(kit.DOCS / filename, heading, subtitle, paragraphs)
    (kit.ROOT / "README.txt").write_text(
        "FICTIONAL SAMPLE PROJECT - FOR BETA TESTING ONLY\n\n"
        f"Project: {kit.TITLE}\nPrimary agency: DPWH\nCollaborator: none\n"
        "Locations: Pasay, Parañaque, Muntinlupa\nStatus: New\n\n"
        "Copy the Contributor Form tab into a new manual project. Save a draft, upload the three separate PDFs, "
        "then submit for validation. The Validator Inputs tab contains provisional testing entries only; "
        "a Validator must inspect the project before using them. No database record, AI analysis, "
        "funding approval, or priority confirmation is created by this kit.\n",
        encoding="utf-8",
    )
    workbook_path = kit.ROOT / "Project_Manual_Entry.xlsx"
    wb = load_workbook(workbook_path, read_only=True)
    assert wb.sheetnames == ["Contributor Form", "Documents and Use", "Validator Inputs"]
    assert sum(value for label, value in kit.FIELDS if label.startswith("Funding Requirement 20")) == 160_000_000
    for filename, _, _, _ in kit.DOCUMENTS:
        path = kit.DOCS / filename
        text = " ".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
        assert kit.MARK in text and kit.TITLE in text and len(text) > 500
        assert path.stat().st_size > 2_000
    destination = kit.ROOT.parent / "RDC-NCR_Second_DPWH_Project_Kit.zip"
    with ZipFile(destination, "w", ZIP_DEFLATED) as archive:
        for path in kit.ROOT.rglob("*"):
            if path.is_file():
                archive.write(path, f"{kit.ROOT.name}/{path.relative_to(kit.ROOT).as_posix()}")
    with ZipFile(destination) as archive:
        saved = load_workbook(BytesIO(archive.read(f"{kit.ROOT.name}/Project_Manual_Entry.xlsx")), read_only=True)
        assert "Validator Inputs" in saved.sheetnames
    print(f"Created {destination} ({destination.stat().st_size:,} bytes), 1 XLSX and 3 validated PDFs")


if __name__ == "__main__":
    main()
