"""Build a manual-entry kit with ten new projects; never connects to the database."""

from __future__ import annotations

import importlib.util
import sys
import zipfile
from collections import Counter
from dataclasses import replace
from pathlib import Path
from shutil import copy2

from openpyxl import load_workbook
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "sample-data-kit-20" / "build_kit.py"
TARGET = ROOT / "RDC-NCR_10_New_Project_Beta_Testing_Kit"
ARCHIVE = ROOT / "RDC-NCR_10_New_Project_Beta_Testing_Kit.zip"

spec = importlib.util.spec_from_file_location("earlier_project_kit", SOURCE)
kit = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = kit
spec.loader.exec_module(kit)
old_titles = {project.title.casefold() for project in kit.PROJECTS}

# Existing catalogue values, committee tracks, form structure, and score weights
# come from the earlier source kit. Every proposal narrative and PDF is new.
SCENARIOS = [
    dict(base=11, number=21, title="Pasig Community Kidney Care and Family Assistance Center", location="Pasig", program="Integrated Community Health and Social Protection Program", description="Develop a community kidney-care center with dialysis referral, screening, nutrition counselling, and family assistance navigation for residents facing long travel and treatment delays.", objective="Improve timely renal care and connect low-income patients with health and social assistance in one service pathway.", scope="Fit out twelve treatment stations, establish screening and counselling rooms, add a family-assistance desk, and coordinate hospital referrals.", outputs="Twelve treatment stations, screening rooms, referral protocols, and an operational assistance desk.", beneficiaries="Residents with chronic kidney disease and caregivers in selected Pasig communities.", beneficiary_count=22000, total_budget=820_000_000, readiness_notes="A facility needs review, patient-flow estimate, site layout, and equipment schedule are available. DOH leads clinical services; DSWD supports assistance referrals and family case navigation.", document_type="Facility Needs Assessment", document_condition="relevant"),
    dict(base=12, number=22, title="San Juan Youth Wellness and Family Guidance Hub", location="San Juan", program="Family Recovery and Community Wellness Program", description="Establish a modest walk-in hub for youth wellbeing sessions, family counselling, and referral to existing health and social welfare services.", objective="Provide an accessible local venue for early family support and appropriate health referrals.", scope="Adapt two counselling rooms, provide group-session space, train intake staff, and prepare a referral directory.", outputs="Two counselling rooms, a group-session area, and a documented referral pathway.", beneficiaries="Adolescents, caregivers, and households seeking early support in selected San Juan barangays.", beneficiary_count=11000, total_budget=135_000_000, readiness_notes="A preliminary service profile is available, but the proposed site agreement and staffing commitments are incomplete. DSWD would lead case support; DOH would receive health referrals.", document_type="Community Service Brief", document_condition="unrelated"),
    dict(base=13, number=23, title="Quezon City Heat Emergency Shelter and Mobile Triage Network", location="Quezon City", program="Community Disaster Preparedness and Social Protection Program", description="Provide cooling shelters and coordinated mobile triage during extreme-heat events across high-exposure communities.", objective="Reduce avoidable heat-related illness and provide safe temporary refuge for vulnerable residents.", scope="Adapt six public shelter sites, equip mobile triage teams, install water and cooling stations, and establish referral procedures.", outputs="Six operational shelter sites, triage equipment, response guides, and coordinated referral links.", beneficiaries="Older persons, children, outdoor workers, and households with limited cooling access.", beneficiary_count=280000, total_budget=1_260_000_000, readiness_notes="A heat-exposure map, shelter assessment, response plan, and equipment inventory are available. DSWD coordinates shelter support while DOH leads triage and clinical referral.", document_type="Heat Response Implementation Plan", document_condition="relevant"),
    dict(base=14, number=24, title="Manila Maternal Nutrition and Early-Care Outreach Stations", location="Manila", program="Integrated Community Health and Social Protection Program", description="Place small maternal nutrition and early-care outreach stations in underserved neighborhoods using existing community spaces.", objective="Improve access to basic pregnancy guidance, child nutrition advice, and appropriate assistance referrals.", scope="Equip four outreach rooms, prepare visit schedules, train staff, and establish a referral process with nearby clinics.", outputs="Four equipped outreach stations, visit schedules, and referral materials.", beneficiaries="Pregnant women, infants, caregivers, and households with limited nearby services.", beneficiary_count=18000, total_budget=165_000_000, readiness_notes="An initial location list and needs summary exist. Site permissions, staffing schedules, and measured demand remain to be confirmed. DOH leads care; DSWD handles family-support referrals.", document_type="Beneficiary Assessment", document_condition="relevant"),
    dict(base=15, number=25, title="Parañaque Coastal Transit Interchange Access Improvement", location="Parañaque", program="Integrated Urban Mobility and River Access Program", description="Improve pedestrian and bus access around a coastal transit interchange where passengers currently cross vehicle lanes and navigate disconnected sidewalks.", objective="Provide safer transfers and more accessible interchange approaches for daily commuters.", scope="Build protected walkways, accessible ramps, bus-bay crossings, drainage connections, signs, and lighting along two interchange approaches.", outputs="Protected approaches, accessible crossings, marked bus bays, and drainage improvements.", beneficiaries="Bus passengers, pedestrians, workers, older persons, and persons with disabilities.", beneficiary_count=190000, total_budget=1_180_000_000, readiness_notes="A passenger movement survey, preliminary traffic plan, access concept, and cost schedule are available. DOTr leads interchange operations; DPWH leads road and drainage works.", document_type="Preliminary Access Engineering Assessment", document_condition="relevant"),
    dict(base=16, number=26, title="Pasay School-Zone Signal and Crossing Coordination Upgrade", location="Pasay", program="Active Transport Safety Network Program", description="Coordinate traffic signals and pedestrian crossing times near selected schools and local transit stops.", objective="Reduce crossing conflicts and make school-zone walking routes easier to use.", scope="Update signal timing at eight junctions, repaint crossings, install warning signs, and conduct a follow-up crossing review.", outputs="Eight retimed junctions, marked crossings, warning signs, and an operations review.", beneficiaries="Students, caregivers, pedestrians, and transit users in selected Pasay streets.", beneficiary_count=26000, total_budget=125_000_000, readiness_notes="An initial junction list and timing observations are available. Detailed pedestrian counts and final coordination with local traffic officers remain incomplete.", document_type="Traffic Operations Note", document_condition="unrelated"),
    dict(base=17, number=27, title="Caloocan Rail-Station Drainage and Multimodal Access Corridor", location="Caloocan", program="Integrated Corridor Safety and Resilience Program", description="Upgrade a station approach corridor affected by stormwater ponding, uneven sidewalks, and conflicts between road vehicles and passengers.", objective="Maintain station access during heavy rain and provide safer walking and public transport connections.", scope="Improve 3.4 kilometres of drainage and pavement, construct accessible walkways, organize loading zones, and add protected crossings.", outputs="Improved drainage and pavement, accessible approaches, marked loading zones, and safer crossings.", beneficiaries="Rail passengers, commuters, nearby residents, small businesses, and emergency vehicles.", beneficiary_count=330000, total_budget=1_520_000_000, readiness_notes="Drainage surveys, traffic observations, utility plans, and preliminary engineering quantities are available. DPWH leads civil works; DOTr coordinates station and transport operations.", document_type="Corridor Engineering Assessment", document_condition="relevant"),
    dict(base=18, number=28, title="Valenzuela Regional Relief Logistics and Evacuation Supply Facility", location="Valenzuela", program="Community Disaster Preparedness and Social Protection Program", description="Develop a logistics facility for pre-positioned evacuation supplies and rapid dispatch to flood-affected communities.", objective="Improve the speed and reliability of family relief support during major emergencies.", scope="Build a flood-resilient storage facility, fit out packing areas, procure inventory equipment, and establish dispatch procedures.", outputs="Operational warehouse, packing area, inventory system, and documented emergency dispatch process.", beneficiaries="Disaster-affected households in Valenzuela and nearby northern Metro Manila communities.", beneficiary_count=410000, total_budget=1_130_000_000, readiness_notes="A site suitability report, flood-elevation review, supply-volume estimate, and logistics plan are available. DSWD would lead storage and emergency distribution.", document_type="Logistics Facility Site Assessment", document_condition="relevant"),
    dict(base=19, number=29, title="Taguig Neighborhood Skills and Assistance Service Hub", location="Taguig", program="Community Livelihood and Family Support Program", description="Provide a neighborhood point for livelihood orientation, skills referrals, and social assistance intake in selected communities.", objective="Improve local access to skills information and family-assistance referrals.", scope="Refurbish a small public service room, provide training equipment, establish an intake desk, and prepare a partner referral directory.", outputs="Refurbished service room, training equipment, intake desk, and referral directory.", beneficiaries="Jobseekers, informal workers, caregivers, and households requesting social assistance.", beneficiary_count=24000, total_budget=185_000_000, readiness_notes="A neighborhood client profile and preliminary room layout exist. Employer links, recurring operating funds, and staffing commitments require further work.", document_type="Community Service Concept Note", document_condition="relevant"),
    dict(base=20, number=30, title="Mandaluyong Community Diagnostic and Remote Consultation Clinic", location="Mandaluyong", program="Primary Care Access Improvement Program", description="Expand a community clinic with basic diagnostics and scheduled remote consultations linked to referral hospitals.", objective="Reduce avoidable travel for routine diagnostic review and improve referral timing.", scope="Adapt three consultation rooms, install basic diagnostic equipment, establish secure consultation scheduling, and train clinical staff.", outputs="Three equipped rooms, a consultation schedule, and an updated referral process.", beneficiaries="Residents with routine diagnostic and follow-up care needs, especially older persons.", beneficiary_count=32000, total_budget=195_000_000, readiness_notes="A clinic service profile and preliminary equipment list are available. Connectivity checks, staffing commitments, and detailed utilization estimates remain incomplete.", document_type="Clinic Service Concept Note", document_condition="none"),
]

STATUSES = {
    21: ("Ongoing", 2025, 44, "Clinic fit-out and equipment procurement are in progress."),
    22: ("Cancelled", 2024, 0, "The proposed building lease was withdrawn; a new site would require a revised proposal."),
    23: ("Completed", 2022, 100, "The six shelter sites and mobile triage arrangements reached final completion."),
    24: ("Not Implemented", None, 0, "Outreach rooms are planned but installation has not started."),
    25: ("New", None, 0, "Interchange access works remain at proposal stage."),
    26: ("Ongoing", 2025, 35, "The first crossing signals and signs are being updated."),
    27: ("On Hold", 2025, 0, "Civil works are paused pending utility relocation and station-access coordination."),
    28: ("Ongoing", 2025, 48, "The storage building and packing area are under construction."),
    29: ("Not Implemented", None, 0, "The service hub has not entered implementation."),
    30: ("New", None, 0, "The clinic extension remains a planned proposal."),
}


def build() -> None:
    if ARCHIVE.exists():
        raise SystemExit("The completed archive already exists; move it before regenerating.")
    TARGET.mkdir(exist_ok=True)
    originals = {project.number: project for project in kit.PROJECTS}
    projects = []
    for row in SCENARIOS:
        base = originals[row["base"]]
        values = {key: value for key, value in row.items() if key != "base"}
        projects.append(replace(base, **values))
    assert len(projects) == 10 and len({p.title for p in projects}) == 10
    assert not ({p.title.casefold() for p in projects} & old_titles)
    assert Counter(p.priority for p in projects) == {"High": 5, "Low": 5}
    assert Counter(p.document_condition for p in projects) == {"relevant": 7, "unrelated": 2, "none": 1}
    assert {p.primary for p in projects} == {"DPWH", "DOH", "DOTr", "DSWD"}
    kit.ROOT = TARGET
    kit.PROJECTS = projects
    kit.STATUS_SCENARIOS = STATUSES
    original_document_instruction = kit.document_instruction
    kit.document_instruction = lambda project: (
        f"Upload the assigned PDF in `supporting-documents/project-{project.number:02d}/`. "
        f"It belongs to Project {({22: 21, 26: 25})[project.number]:02d}, not this project."
        if project.number in {22, 26} else original_document_instruction(project)
    )
    for project in projects:
        kit.write_text(TARGET / "project-data" / f"project-{project.number:02d}.md", kit.project_markdown(project))
        kit.write_text(TARGET / "scoring-references" / f"project-{project.number:02d}-scoring.md", kit.scoring_markdown(project))
        if project.document_condition == "relevant":
            path = TARGET / "supporting-documents" / f"project-{project.number:02d}" / f"{project.code}_{project.document_type.lower().replace(' ', '_')}.pdf"
            path.parent.mkdir(parents=True, exist_ok=True)
            kit.write_pdf(project, path)
    for target_number, source_number in ((22, 21), (26, 25)):
        source = next((TARGET / "supporting-documents" / f"project-{source_number:02d}").glob("*.pdf"))
        destination = TARGET / "supporting-documents" / f"project-{target_number:02d}" / f"P{target_number:02d}_UNRELATED_project_{source_number:02d}.pdf"
        destination.parent.mkdir(parents=True, exist_ok=True)
        copy2(source, destination)
    kit.build_workbook(TARGET / "RDC-NCR_10_New_Projects_Manual_Entry.xlsx")
    kit.write_references()
    matrix = TARGET / "testing-reference" / "agency-collaboration-matrix.md"
    contents = matrix.read_text(encoding="utf-8")
    contents = contents.rsplit("\n", 2)[0] + "\n\nDPWH–DOTr collaborations: Projects 25 and 27. DOH–DSWD collaborations: Projects 21, 22, 23, and 24. Only the primary agency creates and edits the proposal.\n"
    matrix.write_text(contents, encoding="utf-8")
    kit.write_text(TARGET / "README.md", """# RDC-NCR Ten New Project Beta-Testing Kit

These ten proposals (Projects 21–30) are new, distinct scenarios for manual beta testing. They are generated study materials, not approved, funded, submitted, or validated government projects. No database records or accounts were created.

Use `project-data/` or the Excel workbook for Contributor entry. Upload only the PDF assigned in `testing-reference/document-assignment.md`. Projects 22 and 26 deliberately use an unrelated PDF; Project 30 deliberately has no PDF. Enter each Validator Facts Supplement during Validator review. Keep `scoring-references/` and intended priority labels away from Contributor answers, Validator Facts, and PDFs. Compare reference scores only after running the AI Assistant Scorer.

The current published Contributor Form and active scoring rules may differ from the repository defaults used here. Check fields, choice lists, required-document settings, and thresholds before entry. Under a required-document rule, Project 30 is a missing-document validation case and cannot be submitted without a normal Administrator form change. The reference scores are expectations for comparison, not AI outputs or Validator decisions.
""")
    verify(projects)
    with zipfile.ZipFile(ARCHIVE, "w", zipfile.ZIP_DEFLATED) as package:
        for path in TARGET.rglob("*"):
            if path.is_file():
                package.write(path, path.relative_to(ROOT))
    print(f"Created {ARCHIVE}; {ARCHIVE.stat().st_size:,} bytes")


def verify(projects):
    assert len(list((TARGET / "project-data").glob("project-*.md"))) == 10
    assert len(list((TARGET / "scoring-references").glob("project-*-scoring.md"))) == 10
    for p in projects:
        assert sum(amount for _, amount in p.annual_budgets) == p.total_budget
        assert round(sum(weight * raw / 10 for raw, (_, weight) in zip(p.raw_scores, p.criteria)), 2) == p.total_score
        assert (p.total_score >= 70) == (p.priority == "High")
        assert p.title in (TARGET / "project-data" / f"project-{p.number:02d}.md").read_text(encoding="utf-8")
    pdfs = list((TARGET / "supporting-documents").rglob("*.pdf"))
    assert len(pdfs) == 9
    for pdf in pdfs:
        text = " ".join(page.extract_text() or "" for page in PdfReader(pdf).pages)
        assert pdf.stat().st_size > 1000 and len(text.strip()) > 500, pdf
        number = int(pdf.parent.name.split("-")[1])
        target = next(p for p in projects if p.number == number)
        assert (target.title in text) == (target.document_condition == "relevant"), pdf
    book = load_workbook(TARGET / "RDC-NCR_10_New_Projects_Manual_Entry.xlsx", read_only=True)
    assert book["Project Overview"].max_row == 11
    assert book["Scoring Reference"].max_row == 81
    book.close()
    print("Verified ten unique projects, nine readable PDFs, annual budgets, and 80 criterion rows")


if __name__ == "__main__":
    build()
