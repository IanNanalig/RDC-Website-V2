"""Build a manual-entry project data kit; it never connects to Django or a database."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from shutil import copy2
from typing import Iterable

from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


ROOT = Path(__file__).resolve().parent

INFRASTRUCTURE = [
    ("Readiness", 20),
    ("Level of GAD Responsiveness", 15),
    ("Spatial Coverage", 15),
    ("Develop and protect capabilities of individuals and families", 10),
    ("Transform production sector to generate more quality jobs and competitive products", 5),
    ("Achieve seamless and inclusive connectivity", 20),
    ("Provide sustainable energy and water infrastructure", 10),
    ("Support social development through infrastructure", 5),
]

SOCIAL = [
    ("Readiness", 20),
    ("Level of GAD Responsiveness", 15),
    ("Spatial Coverage", 15),
    ("Develop and protect capabilities of individuals and families", 10),
    ("Transform production sector to generate more quality jobs and competitive products", 5),
    ("Promote human and social development", 20),
    ("Reduce vulnerabilities and protect purchasing power", 10),
    ("Increase income-earning ability", 5),
]

READINESS = {
    "completed_documents": "With completed documents such as pre-FS/FS/POW and detailed design, where applicable",
    "ongoing_documents": "Ongoing pre-FS/FS/POW and detailed design, where applicable",
    "project_profile": "With Comprehensive Project Profile",
    "concept_only": "With concept paper/none",
}
GAD = {
    "gender_responsive": "Gender-responsive",
    "gender_sensitive": "Gender-sensitive",
    "promising_prospects": "Promising GAD prospects",
    "invisible": "GAD invisible",
}
SPATIAL = {
    "specific_lgus": "Specific LGUs",
    "region_wide": "Region-wide",
    "interregional": "Interregional",
    "none": "None",
}
REGIONAL_SPATIAL = {
    "single_city": "Single city",
    "eight_to_twelve_lgus": "8 to 12 LGUs",
    "region_wide": "Region-wide",
    "interregional": "Interregional",
}


@dataclass(frozen=True)
class Project:
    number: int
    title: str
    priority: str
    primary: str
    collaborators: tuple[str, ...]
    track: str
    program: str
    location: str
    description: str
    objective: str
    scope: str
    outputs: str
    beneficiaries: str
    beneficiary_count: int
    start_year: int
    end_year: int
    total_budget: int
    budget_weights: tuple[int, ...]
    pcb: str
    chapter: str
    sdgs: tuple[str, ...]
    readiness: str
    gad: str
    spatial: str
    regional_spatial: str
    contributed_outcomes: int
    readiness_notes: str
    document_condition: str
    document_type: str
    raw_scores: tuple[int, ...]

    @property
    def code(self) -> str:
        return f"P{self.number:02d}"

    @property
    def criteria(self) -> list[tuple[str, int]]:
        return INFRASTRUCTURE if self.track == "infrastructure" else SOCIAL

    @property
    def annual_budgets(self) -> list[tuple[int, int]]:
        years = list(range(self.start_year, self.end_year + 1))
        amounts: list[int] = []
        allocated = 0
        for index, weight in enumerate(self.budget_weights):
            amount = self.total_budget - allocated if index == len(self.budget_weights) - 1 else round(self.total_budget * weight / sum(self.budget_weights))
            amounts.append(amount)
            allocated += amount
        return list(zip(years, amounts, strict=True))

    @property
    def total_score(self) -> float:
        return round(sum(weight * score / 10 for score, (_, weight) in zip(self.raw_scores, self.criteria, strict=True)), 2)


PROJECTS = [
    Project(1, "Quezon City Drainage and Flood Control Rehabilitation Program", "High", "DPWH", (), "infrastructure", "Metro Manila Climate-Resilient Infrastructure Program", "Quezon City", "Rehabilitate priority drainage lines, damaged inlets, and outfalls serving flood-prone communities and critical access roads in Quezon City.", "Reduce recurring urban flooding, protect access to schools and health facilities, and improve drainage performance during intense rainfall.", "Survey and rehabilitate 7.2 kilometres of drainage channels, replace catch basins, install debris-control screens, and improve three priority outfalls.", "Rehabilitated drainage segments, improved inlets and outfalls, and safer all-weather access along affected roads.", "Residents, commuters, students, and small businesses in selected Quezon City barangays.", 180000, 2027, 2029, 850_000_000, (30, 40, 30), "Risk Resiliency Program (RRP)", "16 Accelerate Climate Action and Strengthen Disaster Resilience Climate", ("9 - Industry, innovation and infrastructure", "11 - Sustainable cities and communities", "13 - Climate action"), "completed_documents", "gender_sensitive", "specific_lgus", "single_city", 3, "Pre-feasibility study, hydraulic survey, preliminary engineering design, cost estimate, and implementation schedule are available. Priority drainage segments were identified through local flood reports and site inspections.", "relevant", "Project Concept Note", (10, 7, 7, 8, 5, 9, 10, 6)),
    Project(2, "Caloocan Neighborhood Sidewalk Rehabilitation and Lighting Upgrade", "Low", "DPWH", (), "infrastructure", "Safe Local Streets Improvement Program", "Caloocan", "Improve damaged sidewalks and provide pedestrian lighting on selected neighborhood streets near public schools and a local market.", "Provide safer and more accessible walking routes for daily users of selected local streets.", "Replace uneven pavement, add curb ramps, install street lighting, and mark pedestrian crossings on 1.4 kilometres of local roads.", "Accessible sidewalks, curb ramps, lighting fixtures, and marked crossings.", "Students, market visitors, nearby residents, and persons with mobility limitations.", 12000, 2027, 2028, 95_000_000, (60, 40), "PCB on the Sustainable Development Goals (SDGs)", "13 Expand and Upgrade Infrastructure Infrastructure", ("9 - Industry, innovation and infrastructure", "11 - Sustainable cities and communities"), "project_profile", "promising_prospects", "specific_lgus", "single_city", 1, "A project profile and site walk-through notes identify damaged pavement and crossing points. Detailed engineering and a comprehensive accessibility audit remain to be completed.", "relevant", "Site Accessibility Assessment", (4, 4, 4, 4, 2, 5, 2, 3)),
    Project(3, "Manila District Hospital Emergency Department Modernization", "High", "DOH", (), "social", "Urban Emergency Care Capacity Program", "Manila", "Modernize the emergency department of a district hospital to address overcrowding, delayed triage, and limited surge capacity during public health emergencies.", "Improve emergency care access, shorten triage delays, and expand safe treatment capacity for urgent cases.", "Reconfigure triage and treatment zones, upgrade emergency equipment, improve ambulance receiving areas, and train clinical and support personnel.", "Additional treatment bays, upgraded triage area, emergency equipment, and an operational emergency-care workflow.", "Emergency patients, companion caregivers, hospital staff, and residents referred from nearby communities.", 420000, 2027, 2029, 1_100_000_000, (28, 42, 30), "National Program on Population and Family Planning (NPPFP)", "4.1 Boost Health Health & Nutrition", ("3 - Good health and well-being", "5 - Gender equality", "10 - Reduced inequalities"), "ongoing_documents", "gender_responsive", "specific_lgus", "single_city", 3, "Facility assessment, patient-flow study, preliminary equipment list, and phased implementation plan are available. The hospital has identified priority groups including pregnant women, children, older persons, and persons with disabilities.", "relevant", "Facility Needs Assessment", (8, 7, 7, 8, 5, 9, 8, 6)),
    Project(4, "Pasig River Ferry Intermodal Access and Pedestrian Link Project", "High", "DPWH", ("DOTr",), "infrastructure", "Integrated Urban Mobility and River Access Program", "Pasig", "Provide safer pedestrian links, covered walkways, and intermodal access between selected Pasig River ferry stations, nearby public transport, and surrounding streets.", "Improve safe transfers between ferry, road-based public transport, and walking routes while supporting lower-carbon travel.", "Construct covered walkways, accessible ramps, protected crossings, bicycle parking, signage, and station approach improvements.", "Accessible station approaches, protected crossings, covered walkways, and integrated passenger information.", "Ferry passengers, commuters, pedestrians, persons with disabilities, and nearby workers.", 145000, 2027, 2030, 1_200_000_000, (18, 32, 31, 19), "Pasig River Urban Development (PRUD)", "13 Expand and Upgrade Infrastructure Infrastructure", ("9 - Industry, innovation and infrastructure", "11 - Sustainable cities and communities", "13 - Climate action"), "ongoing_documents", "gender_sensitive", "specific_lgus", "single_city", 3, "Concept design, station access survey, preliminary engineering quantities, and coordination notes with ferry and road transport operators are available. Detailed design remains in progress.", "relevant", "Preliminary Engineering Assessment", (8, 7, 7, 7, 5, 10, 5, 6)),
    Project(5, "Navotas Freight Corridor Road Safety and Loading Access Improvements", "Low", "DPWH", ("DOTr",), "infrastructure", "Urban Freight Safety Improvement Program", "Navotas", "Improve loading access and safety markings along a local freight corridor serving fish ports, markets, and nearby residential streets.", "Reduce local conflicts between freight vehicles, pedestrians, and tricycles while improving access to loading areas.", "Install lane markings, loading-bay signs, pedestrian warning devices, and short sidewalk repairs at selected conflict points.", "Marked loading bays, warning devices, short sidewalk repairs, and a local freight access plan.", "Port workers, market vendors, tricycle operators, freight drivers, and residents near selected streets.", 25000, 2027, 2028, 160_000_000, (55, 45), "Pasig River Urban Development (PRUD)", "13 Expand and Upgrade Infrastructure Infrastructure", ("8 - Decent work and economic growth", "9 - Industry, innovation and infrastructure", "11 - Sustainable cities and communities"), "concept_only", "promising_prospects", "specific_lgus", "single_city", 2, "A corridor walk-through and preliminary conflict map are available. Traffic counts, detailed design, and formal loading-area agreements have not yet been completed.", "none", "", (4, 4, 5, 5, 4, 5, 4, 4)),
    Project(6, "Muntinlupa Community Emergency Medical Response Facility", "High", "DOH", (), "social", "Community Emergency Health Resilience Program", "Muntinlupa", "Establish a community emergency medical response facility that coordinates initial stabilization, referral, and ambulance deployment during medical incidents and disasters.", "Improve rapid access to emergency medical support and strengthen referral coordination for vulnerable communities.", "Build a response facility, procure basic stabilization equipment, establish ambulance dispatch space, and train response personnel.", "Operational response facility, equipped stabilization area, dispatch capability, and trained response teams.", "Residents requiring emergency assistance, older persons, children, persons with disabilities, and community responders.", 220000, 2027, 2029, 620_000_000, (25, 45, 30), "Risk Resiliency Program (RRP)", "4.1 Boost Health Health & Nutrition", ("3 - Good health and well-being", "11 - Sustainable cities and communities", "13 - Climate action"), "completed_documents", "gender_responsive", "specific_lgus", "single_city", 3, "Site suitability review, facility layout, equipment schedule, ambulance routing assessment, and implementation timetable are complete. Referral gaps and priority vulnerable groups were documented during community consultations.", "relevant", "Project Implementation Plan", (10, 8, 6, 8, 4, 9, 8, 6)),
    Project(7, "Marikina River Bridge Seismic Retrofit Project", "Low", "DPWH", (), "infrastructure", "Critical Bridge Safety Maintenance Program", "Marikina", "Undertake an initial seismic retrofit of a local bridge crossing used by community traffic and service vehicles.", "Improve structural safety and maintain local access during seismic events.", "Conduct detailed inspection, repair bearings, strengthen selected supports, and update bridge approach markings.", "Inspection report, repaired bearings, strengthened supports, and updated safety markings.", "Nearby households, local commuters, emergency vehicles, and small businesses.", 18000, 2027, 2028, 180_000_000, (48, 52), "Risk Resiliency Program (RRP)", "13 Expand and Upgrade Infrastructure Infrastructure", ("9 - Industry, innovation and infrastructure", "11 - Sustainable cities and communities"), "project_profile", "gender_sensitive", "specific_lgus", "single_city", 1, "A bridge inventory entry and preliminary visual inspection are available. Detailed structural analysis, traffic management design, and finalized cost estimates are pending.", "none", "", (6, 5, 4, 4, 3, 5, 2, 3)),
    Project(8, "Makati Active Transport Wayfinding and Protected Crossing System", "Low", "DOTr", (), "infrastructure", "Active Transport Safety Network Program", "Makati", "Improve pedestrian and cycling wayfinding and install protected crossings at selected local access routes near transit stops and public facilities.", "Make short walking and cycling trips easier to understand and safer at selected crossing locations.", "Install direction signs, pavement markings, protected crossing treatments, and route maps for a limited local network.", "Wayfinding signs, route maps, protected crossings, and marked local cycling connections.", "Pedestrians, cyclists, transit users, and workers in selected Makati streets.", 30000, 2027, 2028, 140_000_000, (58, 42), "PCB on the Sustainable Development Goals (SDGs)", "13 Expand and Upgrade Infrastructure Infrastructure", ("3 - Good health and well-being", "9 - Industry, innovation and infrastructure", "11 - Sustainable cities and communities"), "concept_only", "gender_sensitive", "specific_lgus", "single_city", 1, "A concept route map and initial crossing inventory are available. Detailed safety audit, final route demand assessment, and design drawings are not yet complete.", "unrelated", "", (3, 5, 5, 4, 4, 5, 1, 2)),
    Project(9, "Navotas Primary Care and Maternal Health Satellite Clinic", "Low", "DOH", (), "social", "Community Primary Care Access Program", "Navotas", "Establish a satellite clinic to provide basic primary care, maternal health consultation, and referral support in an underserved coastal community.", "Improve convenient access to preventive and maternal health services for residents with limited nearby clinic options.", "Fit out a leased clinic space, procure basic equipment, schedule outreach sessions, and establish referral arrangements.", "Equipped consultation rooms, maternal health consultation schedule, referral pathway, and outreach sessions.", "Pregnant women, infants, caregivers, older persons, and low-income coastal households.", 36000, 2027, 2029, 175_000_000, (22, 43, 35), "National Program on Population and Family Planning (NPPFP)", "4.1 Boost Health Health & Nutrition", ("3 - Good health and well-being", "5 - Gender equality", "10 - Reduced inequalities"), "project_profile", "gender_sensitive", "specific_lgus", "single_city", 2, "A service-gap profile and preliminary clinic layout are available. Lease finalization, staffing plan, and formal referral agreements remain under development.", "unrelated", "", (5, 6, 5, 7, 3, 6, 4, 2)),
    Project(10, "Valenzuela National Road Pedestrian Accessibility and Drainage Upgrade", "High", "DPWH", (), "infrastructure", "Inclusive National Road Access Program", "Valenzuela", "Upgrade priority pedestrian crossings, sidewalks, drainage inlets, and waiting areas along a national road corridor serving schools, markets, and public transport stops.", "Improve safe and accessible movement while reducing standing water and access disruptions along the corridor.", "Reconstruct sidewalks, install curb ramps and tactile paving, rehabilitate drainage inlets, add protected crossings, and improve waiting areas.", "Accessible sidewalks, curb ramps, tactile paving, rehabilitated inlets, and safer crossings.", "Students, commuters, market users, persons with disabilities, older persons, and roadside workers.", 250000, 2027, 2029, 980_000_000, (27, 43, 30), "Risk Resiliency Program (RRP)", "13 Expand and Upgrade Infrastructure Infrastructure", ("3 - Good health and well-being", "9 - Industry, innovation and infrastructure", "10 - Reduced inequalities", "11 - Sustainable cities and communities"), "completed_documents", "gender_responsive", "specific_lgus", "single_city", 3, "Accessibility audit, drainage inventory, preliminary engineering drawings, traffic observation results, and a phased construction plan are available.", "relevant", "Project Technical Description", (9, 7, 8, 8, 5, 9, 9, 6)),
    Project(11, "Caloocan Integrated Community Health and Family Support Center", "High", "DOH", ("DSWD",), "social", "Integrated Community Health and Social Protection Program", "Caloocan", "Develop a coordinated center that combines primary health navigation, nutrition support, psychosocial first aid, and family case referral for underserved households.", "Improve timely access to health and social protection services through one coordinated community entry point.", "Renovate a service center, establish referral desks, equip consultation and counselling rooms, and implement coordinated case-navigation procedures.", "Operational integrated center, referral desks, consultation rooms, counselling space, and shared case-navigation procedures.", "Low-income households, pregnant women, children, older persons, persons with disabilities, and families requiring social assistance.", 310000, 2027, 2029, 760_000_000, (26, 40, 34), "National Program on Population and Family Planning (NPPFP)", "6.2 Strengthen Social Protection Social Protection", ("1 - No poverty", "3 - Good health and well-being", "5 - Gender equality", "10 - Reduced inequalities"), "completed_documents", "gender_responsive", "specific_lgus", "single_city", 3, "Service-gap mapping, site assessment, preliminary layout, referral protocol, staffing plan, and cost estimate are available. DOH and DSWD roles are documented for health navigation and social assistance referral.", "relevant", "Project Needs Assessment", (10, 8, 7, 8, 5, 9, 8, 7)),
    Project(12, "Pateros Family Recovery and Wellness Center", "Low", "DSWD", ("DOH",), "social", "Family Recovery and Community Wellness Program", "Pateros", "Create a small community center for psychosocial support, family recovery sessions, basic health referral, and case management after local emergencies.", "Provide a safe local venue for family recovery support and coordinated referral after community emergencies.", "Fit out counselling rooms, provide group-session space, establish a referral desk, and prepare a local recovery-session schedule.", "Counselling rooms, group-session area, referral desk, and recovery-session schedule.", "Families affected by local emergencies, caregivers, children, and older persons requiring recovery support.", 15000, 2027, 2028, 150_000_000, (54, 46), "Risk Resiliency Program (RRP)", "6.2 Strengthen Social Protection Social Protection", ("1 - No poverty", "3 - Good health and well-being", "10 - Reduced inequalities"), "project_profile", "gender_sensitive", "specific_lgus", "single_city", 2, "A local needs profile and proposed layout are available. Detailed staffing arrangements, referral protocols, and multi-year operating costs require further development.", "relevant", "Project Concept Note", (4, 5, 5, 6, 2, 6, 6, 3)),
    Project(13, "Manila Emergency Health and Social Assistance Hub", "High", "DSWD", ("DOH",), "social", "Urban Emergency Health and Social Assistance Program", "Manila", "Establish a coordinated emergency hub that links temporary assistance, medical triage referral, psychosocial support, and family case management during large urban incidents.", "Strengthen rapid, coordinated support for households requiring emergency health and social assistance.", "Renovate a hub facility, establish triage referral space, provide temporary assistance counters, equip counselling areas, and implement joint response protocols.", "Emergency hub, triage referral space, assistance counters, counselling areas, and joint response protocols.", "Households affected by emergencies, displaced residents, children, older persons, persons with disabilities, and caregivers.", 450000, 2027, 2030, 1_350_000_000, (17, 29, 33, 21), "Risk Resiliency Program (RRP)", "6.2 Strengthen Social Protection Social Protection", ("1 - No poverty", "3 - Good health and well-being", "5 - Gender equality", "10 - Reduced inequalities", "11 - Sustainable cities and communities"), "completed_documents", "gender_responsive", "specific_lgus", "single_city", 4, "Hazard and service-gap assessment, site due diligence, preliminary design, equipment plan, joint DOH-DSWD response protocol, and phased financing plan are complete.", "relevant", "Project Implementation Plan", (9, 8, 7, 8, 5, 8, 8, 7)),
    Project(14, "Taguig Community Maternal Health and Protection Desk Network", "Low", "DOH", ("DSWD",), "social", "Maternal Health and Protection Access Program", "Taguig", "Set up linked maternal health and protection desks at selected community service points to improve referral, counselling, and access to social assistance.", "Improve early referral and coordinated support for pregnant women and caregivers facing health or protection risks.", "Equip three service desks, train focal staff, prepare referral directories, and establish a case-follow-up schedule.", "Three equipped service desks, trained focal staff, referral directories, and follow-up schedule.", "Pregnant women, new mothers, caregivers, and households requiring health and social protection referrals.", 45000, 2027, 2029, 155_000_000, (25, 41, 34), "National Program on Population and Family Planning (NPPFP)", "4.1 Boost Health Health & Nutrition", ("3 - Good health and well-being", "5 - Gender equality", "10 - Reduced inequalities"), "project_profile", "gender_responsive", "specific_lgus", "single_city", 2, "A preliminary referral map and desk layout are available. Final host-site agreements, training plan, and case workload baseline are pending.", "relevant", "Project Beneficiary Assessment", (5, 6, 6, 6, 3, 6, 5, 3)),
    Project(15, "Quezon City Bus Terminal Access, Safety, and Universal Design Improvements", "High", "DOTr", ("DPWH",), "infrastructure", "Integrated Public Transport Access Program", "Quezon City", "Improve terminal approaches, passenger waiting areas, crossings, and universal-design features around a high-use city bus terminal.", "Increase safe, reliable, and accessible access to public transport for passengers and nearby pedestrians.", "Reconfigure terminal approaches, add protected crossings, improve lighting, construct accessible paths, and install passenger information signs.", "Safer terminal approaches, accessible paths, protected crossings, improved lighting, and passenger information signs.", "Bus passengers, pedestrians, students, workers, older persons, and persons with disabilities.", 380000, 2027, 2029, 1_050_000_000, (24, 45, 31), "PCB on the Sustainable Development Goals (SDGs)", "13 Expand and Upgrade Infrastructure Infrastructure", ("3 - Good health and well-being", "9 - Industry, innovation and infrastructure", "10 - Reduced inequalities", "11 - Sustainable cities and communities"), "ongoing_documents", "gender_sensitive", "specific_lgus", "single_city", 3, "Passenger-count survey, access and safety audit, preliminary design, traffic management concept, and phasing plan are available. Detailed terminal operator coordination is ongoing.", "relevant", "Project Cost Estimate and Implementation Plan", (8, 7, 8, 7, 7, 9, 3, 5)),
    Project(16, "Mandaluyong Local Traffic Signal Timing and Wayfinding Upgrade", "Low", "DOTr", (), "infrastructure", "Local Mobility Operations Improvement Program", "Mandaluyong", "Improve signal timing and directional wayfinding on selected local streets with recurring but localized traffic conflicts.", "Make local intersections easier to navigate and reduce avoidable delay at selected locations.", "Update signal timing plans, replace selected directional signs, and install local intersection markings.", "Updated timing plans, directional signs, and intersection markings.", "Local motorists, pedestrians, public transport users, and nearby businesses.", 28000, 2027, 2028, 110_000_000, (57, 43), "PCB on the Sustainable Development Goals (SDGs)", "13 Expand and Upgrade Infrastructure Infrastructure", ("9 - Industry, innovation and infrastructure", "11 - Sustainable cities and communities"), "project_profile", "promising_prospects", "specific_lgus", "single_city", 1, "A preliminary intersection inventory and local complaints log are available. Signal data collection, detailed traffic modelling, and final sign plans remain incomplete.", "unrelated", "", (4, 4, 4, 4, 4, 5, 1, 2)),
    Project(17, "Taguig C-5 Service Road Safety, Drainage, and Public Transport Access Upgrade", "High", "DPWH", ("DOTr",), "infrastructure", "Integrated Corridor Safety and Resilience Program", "Taguig", "Improve drainage, service-road safety, pedestrian crossings, and public transport access along a high-use section of the C-5 service road.", "Reduce access disruption, improve safe multimodal movement, and strengthen corridor resilience during severe rainfall.", "Rehabilitate drainage inlets, improve service-road pavement, add protected crossings, provide accessible waiting areas, and improve public transport loading access.", "Rehabilitated drainage and pavement, protected crossings, accessible waiting areas, and improved loading access.", "Commuters, pedestrians, roadside workers, transport users, nearby residents, and emergency service vehicles.", 410000, 2027, 2029, 1_450_000_000, (23, 44, 33), "Risk Resiliency Program (RRP)", "13 Expand and Upgrade Infrastructure Infrastructure", ("9 - Industry, innovation and infrastructure", "11 - Sustainable cities and communities", "13 - Climate action"), "completed_documents", "gender_sensitive", "specific_lgus", "single_city", 3, "Drainage inventory, road safety audit, public transport access survey, preliminary engineering drawings, utility coordination notes, and phased cost estimate are complete.", "relevant", "Preliminary Engineering Assessment", (9, 7, 8, 8, 6, 9, 7, 6)),
    Project(18, "Marikina Multi-Hazard Evacuation and Social Welfare Service Center", "High", "DSWD", (), "social", "Community Disaster Preparedness and Social Protection Program", "Marikina", "Develop a multi-hazard evacuation and social welfare service center that provides accessible temporary shelter, family assistance, registration, and referral during disasters.", "Increase safe, dignified, and coordinated support for households displaced by flood, earthquake, or other hazards.", "Construct an accessible evacuation facility, provide family registration and assistance areas, equip counselling space, and establish referral and logistics procedures.", "Accessible evacuation facility, registration and assistance areas, counselling space, and operational referral procedures.", "Disaster-affected households, children, older persons, persons with disabilities, pregnant women, and caregivers.", 360000, 2027, 2030, 1_080_000_000, (18, 31, 32, 19), "Risk Resiliency Program (RRP)", "6.2 Strengthen Social Protection Social Protection", ("1 - No poverty", "3 - Good health and well-being", "5 - Gender equality", "10 - Reduced inequalities", "11 - Sustainable cities and communities", "13 - Climate action"), "completed_documents", "gender_sensitive", "specific_lgus", "single_city", 3, "Hazard exposure review, evacuation gap assessment, site assessment, accessibility layout, equipment schedule, and local referral plan are available.", "relevant", "Site and Facility Assessment", (9, 7, 6, 9, 5, 9, 9, 5)),
    Project(19, "Las Piñas Community Livelihood and Social Services Center", "Low", "DSWD", (), "social", "Community Livelihood and Family Support Program", "Las Piñas", "Improve access to livelihood orientation, family case referral, and basic social services through a small community service center.", "Provide a more accessible local point for livelihood orientation and social service referral.", "Refurbish a service counter, provide training space, install basic case-management equipment, and prepare a referral directory.", "Refurbished service counter, training space, case-management equipment, and referral directory.", "Jobseekers, informal workers, caregivers, low-income households, and individuals seeking social services.", 22000, 2027, 2029, 170_000_000, (24, 39, 37), "PCB on Livelihood and Employment", "5 Increase Income-Earning Ability Skills & Employment", ("1 - No poverty", "8 - Decent work and economic growth", "10 - Reduced inequalities"), "project_profile", "gender_sensitive", "specific_lgus", "single_city", 2, "A local client profile and proposed service layout are available. Target employment pathways, partner commitments, and recurring operating costs need further documentation.", "relevant", "Project Concept Note", (5, 6, 5, 7, 3, 6, 5, 4)),
    Project(20, "Malabon Barangay Primary Care Expansion Clinic", "Low", "DOH", (), "social", "Primary Care Access Improvement Program", "Malabon", "Expand a barangay primary care clinic through additional consultation space, basic diagnostic equipment, and improved referral scheduling.", "Improve convenient access to routine primary care and timely referral for common health needs.", "Refurbish consultation rooms, procure basic diagnostic equipment, improve appointment scheduling, and update the referral directory.", "Refurbished consultation rooms, basic diagnostic equipment, appointment process, and updated referral directory.", "Children, older persons, caregivers, persons with chronic conditions, and low-income households.", 40000, 2027, 2029, 190_000_000, (25, 40, 35), "National Program on Population and Family Planning (NPPFP)", "4.1 Boost Health Health & Nutrition", ("3 - Good health and well-being", "10 - Reduced inequalities"), "project_profile", "gender_sensitive", "specific_lgus", "single_city", 2, "A clinic service profile and preliminary room layout are available. Final equipment specifications, staffing commitments, and detailed patient-demand projections are pending.", "none", "", (5, 6, 5, 6, 3, 6, 4, 2)),
]

# Implementation status is scenario data, separate from proposal review status.
# Dates are adjusted to match the scenario while retaining each project's
# original number of annual funding allocations.
STATUS_SCENARIOS = {
    1: ("Ongoing", 2025, 42, "Drainage surveys and the first rehabilitation package are under way."),
    2: ("Completed", 2024, 100, "The selected sidewalk and lighting works have reached final completion."),
    3: ("Ongoing", 2025, 38, "The first emergency-department work area is being refurbished."),
    4: ("New", None, 0, "Scope and access design are proposed for the future implementation period."),
    5: ("Not Implemented", None, 0, "The access and safety package is scoped but has not started."),
    6: ("Completed", 2023, 100, "Facility works and response-equipment installation are complete."),
    7: ("On Hold", 2025, 0, "The retrofit is paused pending a detailed structural survey and traffic-management plan."),
    8: ("New", None, 0, "The wayfinding network remains at proposal stage."),
    9: ("Not Implemented", None, 0, "The proposed clinic awaits site and lease finalization."),
    10: ("Ongoing", 2025, 46, "Initial crossing and drainage packages are in progress."),
    11: ("Ongoing", 2025, 44, "The center fit-out and referral-desk preparation are in progress."),
    12: ("Cancelled", 2024, 0, "The proposed site is no longer available; a revised location would require a new proposal."),
    13: ("Completed", 2022, 100, "The assistance hub and coordination rooms have reached final completion."),
    14: ("Not Implemented", None, 0, "The desk network has been designed but installation has not started."),
    15: ("New", None, 0, "Terminal-access improvements are proposed for the stated future years."),
    16: ("Ongoing", 2025, 35, "The first signal-timing and sign package is being installed."),
    17: ("On Hold", 2025, 0, "Construction is paused while utility relocation and corridor access are resolved."),
    18: ("Ongoing", 2025, 48, "The evacuation-center shell and service areas are being constructed."),
    19: ("Not Implemented", None, 0, "The service-center proposal has not entered implementation."),
    20: ("New", None, 0, "The primary-care expansion remains a planned proposal."),
}
PROJECTS = [
    replace(project, start_year=(start if start is not None else project.start_year),
            end_year=((start + len(project.budget_weights) - 1) if start is not None else project.end_year))
    for project in PROJECTS
    for _status, start, _progress, _remark in [STATUS_SCENARIOS[project.number]]
]


def implementation_status(project: Project) -> str:
    return STATUS_SCENARIOS[project.number][0]


def status_remark(project: Project) -> str:
    return STATUS_SCENARIOS[project.number][3]


def physical_accomplishment(project: Project) -> str:
    progress = STATUS_SCENARIOS[project.number][2]
    return f"{progress}% of the stated work scope as of November 2026. {status_remark(project)}" if progress else ""


def actual_funding(project: Project) -> list[tuple[int, int | None]]:
    status = implementation_status(project)
    amounts = project.annual_budgets
    if status == "Completed":
        return amounts
    if status == "Ongoing":
        return [(year, round(amount * (0.8 if year < 2026 else 0.35)) if year <= 2026 else None) for year, amount in amounts]
    return [(year, None) for year, _amount in amounts]


def financial_accomplishment(project: Project) -> str:
    if implementation_status(project) not in {"Ongoing", "Completed"}:
        return ""
    disbursed = sum(amount or 0 for _year, amount in actual_funding(project))
    return f"As of November 2026, {money(disbursed)} is recorded against the {money(project.total_budget)} planned requirement."


def funding_source(project: Project) -> str:
    return ("Agency", "LGUs", "NG-Local Funds (GAA)", "ODA")[project.number % 4]


def uacs_code(project: Project) -> str:
    return f"2026-{project.number:04d}" if funding_source(project) == "NG-Local Funds (GAA)" else "Leave blank"


def money(value: int) -> str:
    return f"PHP {value:,.2f}"


def cell(value: object) -> str:
    return str(value).replace("|", "\\|")


def score_reason(project: Project, criterion: str, raw: int) -> str:
    if raw >= 8:
        return f"The documented scope and Validator Facts provide strong, project-specific support for {criterion.lower()}."
    if raw >= 6:
        return f"The proposal supports {criterion.lower()}, with remaining detail or implementation evidence still needed."
    if raw >= 4:
        return f"The proposal identifies a limited basis for {criterion.lower()}, but coverage, evidence, or scale is constrained."
    return f"The proposal currently provides limited support for {criterion.lower()} and needs stronger evidence before a higher score is justified."


def project_markdown(project: Project) -> str:
    collaborators = ", ".join(project.collaborators) if project.collaborators else "None"
    actual_by_year = dict(actual_funding(project))
    budgets = "\n".join(f"| {year} | {money(amount)} | {money(actual_by_year[year]) if actual_by_year[year] is not None else 'Leave blank'} |" for year, amount in project.annual_budgets)
    return f"""# Project {project.number:02d}: {project.title}

## Simplified RDIP Contributor Form values

| Form field | Enter this value |
| --- | --- |
| Agency Name | {project.primary} |
| Collaborating Agencies | {collaborators} |
| Program | {project.program} |
| Project/Activity | {project.title} |
| Location | {project.location} |
| Description | {project.description} |
| Objective | {project.objective} |
| Start Year | {project.start_year} |
| End Year | {project.end_year} |
| Funding Source | {funding_source(project)} |
| UACS Code (if GAA-funded) | {uacs_code(project)} |
| PIP Included | Yes |
| ARNIPAP Included | Yes |
| LUDIP (for SUCs) | Not Applicable |
| IFPs Included | Yes |
| Part of the Convergence Program (PCB) | Yes |
| Convergence Program (PCB) | {project.pcb} |
| RDC-NCR Endorsed | No |
| RDC-NCR Development Sector | {"Sectoral Committee on Infrastructure Development (SCID)" if project.track == "infrastructure" else "Sectoral Committee on Social Development (SCSD)"} |
| RDP-NCR Main Chapter | {project.chapter} |
| Status | {implementation_status(project)} |
| Sustainable Development Goals | {", ".join(project.sdgs)} |
| Physical Accomplishment | {physical_accomplishment(project) or 'Leave blank'} |
| Financial Accomplishment | {financial_accomplishment(project) or 'Leave blank'} |
| Remarks | {status_remark(project) if implementation_status(project) in {'On Hold', 'Cancelled'} else 'Leave blank'} |

## Funding Requirement and Actual/Approved Funding

**Total funding requirement: {money(project.total_budget)}**

| Year | Funding Requirement (PHP) | Actual/Approved Funding (PHP) |
| --- | ---: | --- |
{budgets}

## Project reference details

| Item | Information |
| --- | --- |
| Project scope / major activities | {project.scope} |
| Expected outputs | {project.outputs} |
| Intended beneficiaries | {project.beneficiaries} |
| Estimated beneficiary count | {project.beneficiary_count:,} |

## Validator Facts Supplement

Enter these values only during Validator review.

| Validator field | Select or enter |
| --- | --- |
| Readiness Level | {READINESS[project.readiness]} |
| GAD Responsiveness | {GAD[project.gad]} |
| Spatial Coverage | {SPATIAL[project.spatial]} |
| SCEED Track (if applicable) | Leave as Choose |
| Estimated Beneficiaries | {project.beneficiary_count} |
| Contributed RDP Outcomes | {project.contributed_outcomes} |
| Regional Spatial Category | {REGIONAL_SPATIAL[project.regional_spatial]} |
| Readiness Evidence Notes | {project.readiness_notes} |

## Supporting-document instruction

{document_instruction(project)}
"""


def document_instruction(project: Project) -> str:
    if project.document_condition == "relevant":
        return f"Upload the PDF in `supporting-documents/project-{project.number:02d}/`. It relates to this project."
    if project.document_condition == "none":
        return "Do not upload a supporting document for this project."
    sources = {8: 3, 9: 1, 16: 11}
    return f"Upload the assigned document in `supporting-documents/project-{project.number:02d}/`. It belongs to Project {sources[project.number]:02d}, not this project."


def scoring_markdown(project: Project) -> str:
    rows = []
    for (criterion, weight), raw in zip(project.criteria, project.raw_scores, strict=True):
        contribution = round(weight * raw / 10, 2)
        rows.append(f"| {cell(criterion)} | {weight:g} | {raw:g} | {contribution:.2f} | {score_reason(project, criterion, raw)} |")
    return f"""# Project {project.number:02d} scoring reference

| Item | Reference |
| --- | --- |
| Project title | {project.title} |
| Expected classification | {project.priority} |
| Reference total | {project.total_score:.2f} / 100 |
| High-priority threshold | 70.00 / 100 |

| Criterion | Weight | Raw score (0–10) | Weighted contribution | Reference rationale |
| --- | ---: | ---: | ---: | --- |
{chr(10).join(rows)}

The total is the sum of `weight × raw score ÷ 10`. This reference is for tester comparison only; enter project data and Validator Facts through the portal, run the AI Assistant Scorer, and make the actual Validator decision in the application.
"""


def write_pdf(project: Project, target: Path) -> None:
    styles = getSampleStyleSheet()
    title = styles["Title"]
    heading = styles["Heading2"]
    body = styles["BodyText"]
    body.leading = 14
    doc = SimpleDocTemplate(str(target), pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm)
    table_data = [
        ["Originating agency", project.primary],
        ["Collaborating agency", ", ".join(project.collaborators) or "None"],
        ["Project location", project.location],
        ["Implementation status", implementation_status(project)],
        ["Implementation period", f"{project.start_year}–{project.end_year}"],
        ["Indicative total cost", money(project.total_budget)],
    ]
    story = [
        Paragraph(project.document_type, title),
        Paragraph(project.title, heading),
        Paragraph("Prepared for project development and technical review · 04 November 2026", body),
        Spacer(1, 6 * mm),
        Table(table_data, colWidths=[48 * mm, 122 * mm], style=TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#E8F0F8")),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#94A3B8")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ])),
        Spacer(1, 6 * mm),
        Paragraph("Project need and proposed response", heading),
        Paragraph(project.description + " " + project.objective, body),
        Spacer(1, 3 * mm),
        Paragraph("Scope and deliverables", heading),
        Paragraph(project.scope + " Expected outputs include " + project.outputs, body),
        Spacer(1, 3 * mm),
        Paragraph("Implementation position", heading),
        Paragraph(physical_accomplishment(project) or status_remark(project), body),
        Spacer(1, 3 * mm),
        Paragraph("Beneficiary and implementation context", heading),
        Paragraph(f"The project is intended to benefit {project.beneficiaries} The working beneficiary estimate is {project.beneficiary_count:,}. {project.readiness_notes}", body),
        Spacer(1, 3 * mm),
        Paragraph("Indicative annual financing", heading),
        Table([[str(year), money(amount)] for year, amount in project.annual_budgets], colWidths=[45 * mm, 60 * mm], style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#94A3B8")),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ])),
    ]
    doc.build(story)


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip() + "\n", encoding="utf-8")


def excel_table(sheet, headers: list[str], rows: Iterable[Iterable[object]], widths: list[int]) -> None:
    sheet.append(headers)
    for row in rows:
        sheet.append(list(row))
    header_fill = PatternFill("solid", fgColor="0F4C5C")
    for cell_ in sheet[1]:
        cell_.font = Font(color="FFFFFF", bold=True)
        cell_.fill = header_fill
        cell_.alignment = Alignment(wrap_text=True, vertical="top")
    for row in sheet.iter_rows(min_row=2):
        for cell_ in row:
            cell_.alignment = Alignment(wrap_text=True, vertical="top")
    for index, width in enumerate(widths, start=1):
        sheet.column_dimensions[get_column_letter(index)].width = width
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions


def build_workbook(destination: Path) -> None:
    wb = Workbook()
    overview = wb.active
    overview.title = "Project Overview"
    excel_table(overview,
        ["No.", "Project Title", "Primary Agency", "Collaborating Agency", "Priority Reference", "Reference Score", "Implementation Status", "Funding Source", "Total Budget (PHP)", "Document Condition", "Location"],
        [(p.number, p.title, p.primary, ", ".join(p.collaborators), p.priority, p.total_score, implementation_status(p), funding_source(p), p.total_budget, p.document_condition.title(), p.location) for p in PROJECTS],
        [8, 52, 16, 20, 17, 16, 20, 22, 20, 20, 20],
    )
    overview.conditional_formatting.add("E2:E21", CellIsRule(operator="equal", formula=['"High"'], fill=PatternFill("solid", fgColor="C6EFCE")))
    overview.conditional_formatting.add("E2:E21", CellIsRule(operator="equal", formula=['"Low"'], fill=PatternFill("solid", fgColor="FCE4D6")))
    for row in overview.iter_rows(min_row=2, min_col=9, max_col=9):
        row[0].number_format = '#,##0.00'

    form = wb.create_sheet("Contributor Form Entry")
    excel_table(form,
        ["No.", "Agency Name", "Collaborating Agencies", "Program", "Project/Activity", "Location", "Description", "Objective", "Start Year", "End Year", "Funding Source", "UACS Code", "PIP", "ARNIPAP", "LUDIP", "IFPs", "PCB Included", "PCB Program", "RDC-NCR Endorsed", "Development Sector", "RDP-NCR Main Chapter", "Status", "SDG Selections", "Physical Accomplishment", "Financial Accomplishment", "Remarks", "Scope / Activities", "Expected Outputs", "Beneficiaries"],
        [(p.number, p.primary, ", ".join(p.collaborators), p.program, p.title, p.location, p.description, p.objective, p.start_year, p.end_year, funding_source(p), uacs_code(p), "Yes", "Yes", "Not Applicable", "Yes", "Yes", p.pcb, "No", "Sectoral Committee on Infrastructure Development (SCID)" if p.track == "infrastructure" else "Sectoral Committee on Social Development (SCSD)", p.chapter, implementation_status(p), ", ".join(p.sdgs), physical_accomplishment(p), financial_accomplishment(p), status_remark(p) if implementation_status(p) in {"On Hold", "Cancelled"} else "", p.scope, p.outputs, p.beneficiaries) for p in PROJECTS],
        [6, 15, 20, 36, 48, 18, 58, 52, 10, 10, 20, 16, 8, 10, 16, 8, 14, 31, 18, 38, 40, 12, 38, 52, 52, 52, 60, 55, 50],
    )

    funding = wb.create_sheet("Funding")
    funding_rows = []
    for p in PROJECTS:
        for year, amount in p.annual_budgets:
            funding_rows.append((p.number, p.title, year, amount, dict(actual_funding(p))[year], p.total_budget))
    excel_table(funding, ["No.", "Project Title", "Year", "Funding Requirement (PHP)", "Actual/Approved Funding (PHP)", "Total Project Cost (PHP)"], funding_rows, [6, 52, 10, 26, 28, 24])
    for row in funding.iter_rows(min_row=2, min_col=4, max_col=6):
        for cell_ in row:
            cell_.number_format = '#,##0.00'

    facts = wb.create_sheet("Validator Facts")
    excel_table(facts,
        ["No.", "Project Title", "Readiness Level", "GAD Responsiveness", "Spatial Coverage", "SCEED Track", "Estimated Beneficiaries", "Contributed RDP Outcomes", "Regional Spatial Category", "Readiness Evidence Notes"],
        [(p.number, p.title, READINESS[p.readiness], GAD[p.gad], SPATIAL[p.spatial], "Leave as Choose", p.beneficiary_count, p.contributed_outcomes, REGIONAL_SPATIAL[p.regional_spatial], p.readiness_notes) for p in PROJECTS],
        [6, 52, 49, 28, 20, 18, 24, 26, 28, 70],
    )

    scores = wb.create_sheet("Scoring Reference")
    score_rows = []
    for p in PROJECTS:
        for (criterion, weight), raw in zip(p.criteria, p.raw_scores, strict=True):
            score_rows.append((p.number, p.title, p.priority, criterion, weight, raw, round(weight * raw / 10, 2), score_reason(p, criterion, raw), p.total_score))
    excel_table(scores, ["No.", "Project Title", "Expected Priority", "Criterion", "Weight", "Raw Score (0–10)", "Weighted Contribution", "Reference Rationale", "Total Score"], score_rows, [6, 50, 16, 58, 10, 18, 22, 72, 14])
    for row in scores.iter_rows(min_row=2, min_col=5, max_col=9):
        for cell_ in row:
            if cell_.column in {5, 6, 7, 9}:
                cell_.number_format = '0.00'

    documents = wb.create_sheet("Document Assignments")
    sources = {8: 3, 9: 1, 16: 11}
    excel_table(documents,
        ["No.", "Project Title", "Condition", "Manual upload instruction"],
        [(p.number, p.title, p.document_condition.title(), document_instruction(p)) for p in PROJECTS],
        [6, 58, 18, 82],
    )

    notes = wb.create_sheet("Read Me")
    notes.append(["RDC-NCR 20-Project Manual Beta-Testing Kit"])
    notes.append(["Use the Contributor Form Entry and Funding sheets for manual portal entry. Use Validator Facts during Validator review. Keep Scoring Reference and expected priority labels out of AI input fields and supporting uploads."])
    notes.append(["All materials are internal testing references. They are not approved projects, validator decisions, or database records."])
    notes.column_dimensions["A"].width = 120
    for row in notes.iter_rows():
        for cell_ in row:
            cell_.alignment = Alignment(wrap_text=True, vertical="top")
    notes["A1"].font = Font(bold=True, size=14)
    notes["A1"].fill = PatternFill("solid", fgColor="0F4C5C")
    notes["A1"].font = Font(color="FFFFFF", bold=True, size=14)
    destination.parent.mkdir(parents=True, exist_ok=True)
    wb.save(destination)


def write_references() -> None:
    overview_rows = "\n".join(f"| {p.number:02d} | {p.title} | {p.primary} | {', '.join(p.collaborators) or '—'} | {p.priority} | {implementation_status(p)} | {funding_source(p)} | {money(p.total_budget)} | {p.document_condition} |" for p in PROJECTS)
    write_text(ROOT / "testing-reference" / "project-overview.md", f"""# Consolidated project overview

| No. | Project Title | Primary Agency | Collaborating Agency | Intended Priority | Implementation Status | Funding Source | Total Project Cost | Document Condition |
| ---: | --- | --- | --- | --- | --- | --- | ---: | --- |
{overview_rows}
""")
    status_rows = "\n".join(
        f"| {p.number:02d} | {p.title} | {implementation_status(p)} | {p.start_year}–{p.end_year} | {physical_accomplishment(p) or 'Not applicable'} | {financial_accomplishment(p) or 'Not applicable'} | {status_remark(p)} |"
        for p in PROJECTS
    )
    write_text(ROOT / "testing-reference" / "implementation-status-matrix.md", f"""# Implementation status matrix

These are proposal-form implementation statuses, not submission or validation decisions. Every project still follows the same Contributor submission and Validator review process.

| No. | Project | Status | Implementation years | Physical accomplishment | Financial accomplishment | Explanation |
| ---: | --- | --- | --- | --- | --- | --- |
{status_rows}
""")
    collabs = [p for p in PROJECTS if p.collaborators]
    collab_rows = "\n".join(f"| {p.number:02d} | {p.primary} | {', '.join(p.collaborators)} | {p.title} |" for p in collabs)
    write_text(ROOT / "testing-reference" / "agency-collaboration-matrix.md", f"""# Agency collaboration matrix

| Project | Primary agency | Collaborating agency | Project |
| ---: | --- | --- | --- |
{collab_rows}

DPWH–DOTr collaborations: Projects 04, 05, 15, and 17. DOH–DSWD collaborations: Projects 11, 12, 13, and 14. Only the primary agency should create and edit the proposal; the collaborating agency is used to test view-only collaboration access.
""")
    doc_rows = "\n".join(f"| {p.number:02d} | {p.document_condition.title()} | {document_instruction(p)} |" for p in PROJECTS)
    write_text(ROOT / "testing-reference" / "document-assignment.md", f"""# Supporting-document assignment

| Project | Condition | Tester instruction |
| ---: | --- | --- |
{doc_rows}

Do not upload scoring references, this README, or a project file as evidence.
""")
    fact_rows = "\n".join(f"| {p.number:02d} | {READINESS[p.readiness]} | {GAD[p.gad]} | {SPATIAL[p.spatial]} | {p.beneficiary_count:,} | {p.contributed_outcomes} | {REGIONAL_SPATIAL[p.regional_spatial]} |" for p in PROJECTS)
    write_text(ROOT / "testing-reference" / "validator-facts-reference.md", f"""# Validator Facts Supplement reference

| Project | Readiness | GAD | Spatial coverage | Beneficiaries | RDP outcomes | Regional spatial category |
| ---: | --- | --- | --- | ---: | ---: | --- |
{fact_rows}

The full project-specific readiness notes are in each `project-data` file and in the Excel workbook.
""")
    write_text(ROOT / "testing-reference" / "beta-testing-workflow.md", """# Manual beta-testing workflow

1. Create the Contributor account through the portal using the project primary agency.
2. Enter one project from `project-data` through the Simplified RDIP Contributor Form. Do not use database imports.
3. Save the proposal, apply its stated document condition, then submit when the ordinary form requirements are satisfied.
4. Confirm that a collaborating agency can view but cannot edit a joint proposal.
5. As a Validator, enter the corresponding Validator Facts Supplement, run the AI Assistant Scorer, compare the outcome with the separate scoring reference, and test permitted score adjustments.
6. Keep all actual validation, confirmation, and endorsement decisions in the normal workflow. The reference classification is not a decision.
""")
    rubric_rows = "\n".join(f"| {name} | {weight} |" for name, weight in INFRASTRUCTURE)
    social_rows = "\n".join(f"| {name} | {weight} |" for name, weight in SOCIAL)
    write_text(ROOT / "scoring-references" / "scoring-rubric-reference.md", f"""# Scoring rubric reference

Reference source: current application default priority-rule configuration. Scores use `weight × raw score ÷ 10`; a high-priority reference score is 70.00 or greater.

## Infrastructure track

| Criterion | Weight |
| --- | ---: |
{rubric_rows}

## Social track

| Criterion | Weight |
| --- | ---: |
{social_rows}
""")


def build() -> None:
    if len(PROJECTS) != 20:
        raise ValueError("The kit requires exactly 20 projects.")
    if sum(p.priority == "High" for p in PROJECTS) != 10 or sum(p.priority == "Low" for p in PROJECTS) != 10:
        raise ValueError("The kit requires ten High and ten Low reference projects.")
    if sum(p.document_condition == "relevant" for p in PROJECTS) != 14:
        raise ValueError("The kit requires fourteen relevant documents.")
    if sum(p.document_condition == "none" for p in PROJECTS) != 3 or sum(p.document_condition == "unrelated" for p in PROJECTS) != 3:
        raise ValueError("The kit requires three no-document and three unrelated-document cases.")
    for project in PROJECTS:
        if len(project.raw_scores) != len(project.criteria):
            raise ValueError(f"Project {project.number} lacks a criterion score.")
        if sum(amount for _, amount in project.annual_budgets) != project.total_budget:
            raise ValueError(f"Project {project.number} budget does not reconcile.")
        if project.priority == "High" and (project.total_score < 70 or project.total_budget < 200_000_000):
            raise ValueError(f"Project {project.number} is not a valid high-priority reference.")
        if project.priority == "Low" and project.total_score >= 70:
            raise ValueError(f"Project {project.number} is not a valid low-priority reference.")

    write_text(ROOT / "README.md", """# RDC-NCR 20-Project Manual Beta-Testing Data Kit

This is an internal data-entry and AI-evaluation reference kit. It contains no database fixture, user account, validation decision, project submission, or AI analysis. The materials must not be represented as approved or funded government projects.

## Use

1. Manually enter a project through the Contributor interface using `project-data` or the Excel workbook.
2. Upload only the PDF directed by `testing-reference/document-assignment.md`.
3. Enter the matching Validator Facts Supplement only during Validator review.
4. Use the scoring references only after the AI Assistant Scorer has run; do not copy priority labels or expected scores into an AI input or supporting document.

The kit has 20 projects: 10 High and 10 Low reference classifications, four DPWH–DOTr collaborations, four DOH–DSWD collaborations, 14 relevant documents, three no-document cases, and three unrelated-document cases.

## Before data entry

Check the currently published Contributor Form and active AI scoring configuration. This kit follows the repository's default form and rubric; an Administrator can publish different options or scoring weights. The repository's default Supporting Documents field requires at least one file, so the three no-document cases cannot be submitted under that default. Use them to test the missing-document validation, or have an Administrator publish a form that makes evidence optional before testing submission. Do not attach unrelated evidence merely to bypass a required-file rule.

The default form also requires a UACS Code when Funding Source is NG-Local Funds (GAA). The sample codes in this kit are fictional entry values for that condition. Keep scoring references separate from Contributor form answers, Validator Facts, and PDFs.
""")
    for project in PROJECTS:
        write_text(ROOT / "project-data" / f"project-{project.number:02d}.md", project_markdown(project))
        write_text(ROOT / "scoring-references" / f"project-{project.number:02d}-scoring.md", scoring_markdown(project))

    for project in PROJECTS:
        if project.document_condition != "relevant":
            continue
        target = ROOT / "supporting-documents" / f"project-{project.number:02d}" / f"{project.code}_{project.document_type.lower().replace(' ', '_')}.pdf"
        target.parent.mkdir(parents=True, exist_ok=True)
        write_pdf(project, target)

    for target_number, source_number in {8: 3, 9: 1, 16: 11}.items():
        source = next((ROOT / "supporting-documents" / f"project-{source_number:02d}").glob("*.pdf"))
        target = ROOT / "supporting-documents" / f"project-{target_number:02d}" / f"P{target_number:02d}_upload_document_from_project_{source_number:02d}.pdf"
        target.parent.mkdir(parents=True, exist_ok=True)
        copy2(source, target)

    write_references()
    build_workbook(ROOT / "RDC-NCR_20_Project_Manual_Beta_Testing_Kit.xlsx")
    print(f"Created {len(PROJECTS)} project files in {ROOT}")
    print(f"Created workbook: {ROOT / 'RDC-NCR_20_Project_Manual_Beta_Testing_Kit.xlsx'}")


if __name__ == "__main__":
    build()
