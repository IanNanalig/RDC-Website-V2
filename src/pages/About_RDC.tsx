import React, { useState } from "react";
import annexA from "../assets/Documents/Annex_A__20020717-EO-0113-GMA.pdf";
import annexB from "../assets/Documents/Annex_B_MMDA-Reso-02-47.pdf";

type LegalDocument = {
  id: string;
  title: string;
  description: string;
  icon: string;
  color: string;
  url: string;
  fileType: string;
  fileSize?: string;
  pages?: number;
};

const LEGAL_DOCUMENTS: LegalDocument[] = [
  {
    id: "eo113",
    title: "Executive Order No. 113",
    description:
      "Redefining the functions and composition of the Regional Development Council, establishing the framework for regional planning and development coordination.",
    icon: "📜",
    color: "from-blue-600 to-cyan-500",
    url: annexA,
    fileType: "PDF",
    fileSize: "1.1 MB",
    pages: 24,
  },
  {
    id: "mmda",
    title: "MMDA Resolution No. 02-47",
    description:
      "Metropolitan Manila Development Authority resolution establishing coordination mechanisms and procedures for regional development activities.",
    icon: "⚖️",
    color: "from-green-600 to-emerald-500",
    url: annexB,
    fileType: "PDF",
    fileSize: "10.8 MB",
    pages: 32,
  },
  {
    id: "manual",
    title: "RDC-NCR Manual",
    description:
      "Comprehensive operational manual detailing the policies, procedures, and guidelines for the functioning of the Regional Development Council.",
    icon: "📖",
    color: "from-orange-600 to-red-500",
    url: "https://online.fliphtml5.com/igerd/gdgp/#p=32",
    fileType: "PDF",
    fileSize: "5.6 MB",
    pages: 56,
  },
];

// Committee Data
type Committee = {
  id: string;
  title: string;
  description: string;
  icon: string;
  color: string;
  content: {
    overview: string;
    functions: string[];
    members: string[];
  };
};

const COMMITTEES: Committee[] = [
  {
    id: "executive",
    title: "Executive Committee",
    description: "Acts on matters requiring immediate RDC attention",
    icon: "👑",
    color: "from-purple-500 to-purple-600",
    content: {
      overview:
        "The Council shall create an Executive Committee to act on matters that require immediate attention for and on behalf of the RDC when it is not in session.",
      functions: [],
      members: [
        "RDC Chairperson or his duly appointed or designated Chairperson of the Executive Committee",
        "the RDC Secretary as the Secretary of the Executive Committee",
        "the Four (4) Sectoral Committee Chairpersons",
        "Private Sector/NGO Representatives",
        "the Mayors who compose the Executive Committee of the Metro Manila Council",
      ],
    },
  },
  {
    id: "sectoral",
    title: "Sectoral Committees",
    description: "Four specialized development committees",
    icon: "🏛️",
    color: "from-amber-500 to-amber-600",
    content: {
      overview:
        "Four major sectoral committees addressing specific development areas in the region.",
      functions: [],
      members: [
        "1. Sectoral Committee on Economic and Environment Development (SCEED)",
        "2. Sectoral Committee on Social Development (SCSD)",
        "3. Sectoral Committee on Infrastructure Development (SCID)",
        "4. Sectoral Committee on Finance and Development Administration (SCFDA)",
      ],
    },
  },
  {
    id: "special",
    title: "Special Committees",
    description: "Technical and specialized advisory committees",
    icon: "🔍",
    color: "from-rose-500 to-rose-600",
    content: {
      overview:
        "Special committees created for specific technical functions and regional initiatives.",
      functions: [],
      members: [
        "1. Regional Project Monitoring and Evaluation Systems (RPMES)",
        "2. Regional Land Use Committee (RLUC)",
        "3. Regional Research Development and Innovation Committee (RRDIC)",
        "4. Regional Competitiveness Program Committee (RCPC)",
        "5. Regional Committee on Devolution (ComDev-NCR)",
      ],
    },
  },
  {
    id: "affiliate",
    title: "Affiliate Committees",
    description: "Support committees under RDC umbrella",
    icon: "🤝",
    color: "from-indigo-500 to-indigo-600",
    content: {
      overview:
        "Affiliate inter-agency committees recognized by RDC-NCR to assist in coordination, monitoring and evaluation of specific concerns.",
      functions: [],
      members: [
        "1. Regional Committee for the Welfare of Children (RCWC)",
        "2. Regional Small and Medium Enterprise Development Council (RSMEDC)",
        "3. Regional Statistical Committee (RSC)",
        "4. Regional Peace and Order Council (RPOC)",
      ],
    },
  },
  {
    id: "advisory",
    title: "Advisory Committees",
    description: "Expert consultation bodies",
    icon: "💡",
    color: "from-slate-500 to-slate-600",
    content: {
      overview:
        "Members from the House of Representatives who are designated as part of the SNVMs may constitute the Advisory Committee of the Regional Development Council.",
      functions: [],
      members: [
        "Members of the House of Representatives (designated as Special Non-Voting Members)",
        "Expert advisors and consultants",
        "Academic representatives",
      ],
    },
  },
];

// Detailed Committee Data for Detailed Modal
type DetailedCommittee = {
  id: string;
  title: string;
  overview: string;
  functions: string[];
  members: string[];
  subSections?: Array<{
    title: string;
    content: string[];
  }>;
};

const DETAILED_COMMITTEES: { [key: string]: DetailedCommittee } = {
  sectoral: {
    id: "sectoral",
    title: "Sectoral Committees",
    overview: "Four major committees addressing specific development sectors",
    functions: [],
    members: [],
    subSections: [
      {
        title:
          "1. Sectoral Committee on Economic and Environment Development (SCEED)",
        content: [
          "Addresses economic concerns in industry, trade, labor, tourism, environment and natural resources, science and technology",
          "Acts as principal facilitator of economic development in the region",
          "Functions:",
          "- Recommend government policies, programs and projects on economic development",
          "- Spearhead budget hearings of sectoral regional line agencies",
          "- Integrate sectoral plans of LGUs into regional plans",
          "- Analyze sectoral information for regional development reports",
        ],
      },
      {
        title: "2. Sectoral Committee on Social Development (SCSD)",
        content: [
          "Reviews and evaluates major social development issues on health, nutrition, population, manpower development, social welfare, community development and housing",
          "Functions:",
          "- Recommend government policies, programs and projects on social development",
          "- Spearhead budget hearings of key regional line agencies, SUCs",
          "- Integrate social development plans of LGUs into regional plans",
          "Sub-Committee on Social Protection (SCSP):",
          "- Develop 5-year Social Protection Plan",
          "- Recommend policies and strategies for social protection",
          "- Coordinate preparation of regular assessment reports",
        ],
      },
      {
        title: "3. Sectoral Committee on Infrastructure Development (SCID)",
        content: [
          "Addresses infrastructure sector concerns: transportation, communications, water resources, power generation and electrification, social infrastructure",
          "Functions:",
          "- Recommend government policies, programs and projects on infrastructure",
          "- Spearhead budget hearings of key sectors regional line agencies",
          "- Integrate infrastructure development plans of LGUs",
          "- Provide technical support to infrastructure sub-committees",
        ],
      },
      {
        title:
          "4. Sectoral Committee on Finance and Development Administration (SCFDA)",
        content: [
          "Coordinates formulation, implementation, monitoring of development administration framework",
          "Looks into scope and size of government activities, decision-making, capability building, bureaucratic performance, streamlining of government machinery",
          "Functions:",
          "- Coordinate formulation/updating of Development Administration framework",
          "- Recommend government policies on development administration",
          "- Assess annual performance of Development Administration sector",
          "- Serve as forum for discussing policy issues",
          "- Serve as Oversight Committee of the RDC",
        ],
      },
    ],
  },
  special: {
    id: "special",
    title: "Special Committees",
    overview: "Technical committees for specific regional initiatives",
    functions: [],
    members: [],
    subSections: [
      {
        title: "1. Regional Project Monitoring and Evaluation Systems (RPMES)",
        content: [
          "Primary aim: Expedite project implementation and develop project facilitation, problem-solving, monitoring and evaluation",
          "Functions:",
          "- Provide up-to-date information on project implementation status",
          "- Identify bottlenecks for remedial actions",
          "- Integrate all monitoring activities in the region",
          "- Assess if projects support regional development goals",
        ],
      },
      {
        title: "2. Regional Land Use Committee (RLUC)",
        content: [
          "Strengthened under Executive Order No. 770 Series of 2008",
          "Functions:",
          "- Formulate and update Regional Physical Framework Plan (RPFP)",
          "- Promote integration of land use and physical planning policies",
          "- Decide and resolve region-specific land use policy conflicts",
          "- Review and recommend actions on land use policy conflicts",
        ],
      },
      {
        title:
          "3. Regional Research Development and Innovation Committee (RRDIC)",
        content: [
          "Officially recognized through RDC-NCR Resolution No. 02, Series of 2021",
          "Functions:",
          "- Recommend R&D investment of SUCs for efficient allocation of government funds",
          "- Review SUCs' R&D agenda for alignment with NCR R&D agenda",
          "- Evaluate and endorse R&D infrastructure projects requiring huge budgets",
          "Composition:",
          "- Chairperson: DOST-NCR",
          "- Vice-Chairperson: MMDA",
          "- Members: DENR-NCR, DOH-MMCHD, DILG-NCR, DA-BAR, CHED-NCR, DTI, PSA-NCR, Industry/Sector representatives, City/Municipality Planning Officers",
        ],
      },
      {
        title: "4. Regional Competitiveness Program Committee (RCPC)",
        content: [
          "Established through RDC-NCR Resolution No. 3, Series of 2021",
          "Responsible for advocating and ensuring implementation of Competitiveness Roadmap",
          "Functions:",
          "- Monitor competitiveness level through annual RRC ranking",
          "- Recommend programs to improve competitiveness of Metro Manila LGUs",
          "- Collaborate for investment promotion activities",
          "- Provide policy recommendations to RDC",
          "Composition:",
          "- Chairperson: DTI-NCRO",
          "- Co-Chairperson: PCCI",
          "- Members: DOST-NCR, PSA, DPWH-NCR, PFTI, MMAE, City of Manila, Valenzuela Polytechnic, University of the Philippines",
        ],
      },
      {
        title: "5. Regional Committee on Devolution (ComDev-NCR)",
        content: [
          "Officially recognized on 21 December 2021",
          "Established through Sec. 8 of IRR of EO No. 138 series of 2021",
          "Functions:",
          "- Monitor and evaluate implementation of Devolution Transition Plans (DTPs)",
          "- Identify and respond to regional/local specific issues",
          "- Coordinate with NGAs and LGUs for smooth transition",
          "- Submit quarterly reports to ComDev and RDC",
          "Composition:",
          "- Chairperson: DBM-NCR Regional Director",
          "- Co-Chairperson: DILG-NCR",
          "- Members: NEDA, BLGF, DA, DENR-NCR, DOLE-NCR, DSWD-NCR, DOT-NCR, DOH-MMCHD, DTI-NCR, MMDA, PIA-NCR, League of Municipalities, League of Cities",
        ],
      },
    ],
  },
  affiliate: {
    id: "affiliate",
    title: "Affiliate Committees",
    overview:
      "Committees recognized under RDC-NCR umbrella for specific concerns",
    functions: [],
    members: [],
    subSections: [
      {
        title: "1. Regional Committee for the Welfare of Children (RCWC)",
        content: [
          "Regional counterpart of Children Welfare Council (CWC)",
          "Serves as link between national and local government on child rights policies",
          "Functions (4 clusters):",
          "- Advocacy on Policies and Programs for Children",
          "- Coordinate Planning, Implementation, Monitoring and Evaluation",
          "- Provide Technical Assistance to Local Councils",
          "- Provide Status Reports to concerned government bodies",
          "Composition:",
          "- Chairperson: DSWD-NCR",
          "- Members: DepEd, DOH, DOLE, DOJ, DILG, DA, NEDA, NNC, CWC",
          "- At least 3 NGO representatives, youth representative",
          "- Secretariat: DSWD Regional Office",
        ],
      },
      {
        title:
          "2. Regional Small and Medium Enterprise Development Council (RSMEDC)",
        content: [
          "Compliance with RA 6298 Magna Carta for Small Enterprises",
          "Objectives:",
          "- Serve as forum for SME issues and concerns",
          "- Synchronize programs and services for SME development",
          "- Advocate policies and provide directions for SMEs",
          "- Come up with accurate, updated database on SMEs",
          "Composition:",
          "- Chairperson: DTI-NCRO",
          "- Co-Chairperson: PCCI",
          "- Members: DOST-NCR, DOLE-NCR, DOT-NCR, DENR-NCR, DA, TESDA-NCR, PIA-NCR, SBCorp",
        ],
      },
      {
        title: "3. Regional Statistical Committee (RSC)",
        content: [
          "Formerly Regional Statistical Coordinating Committee",
          "Tasks: Provide direction and guidance to regional/local statistical development activities",
          "Serves as policymaking body on statistical matters",
          "Composition:",
          "- Chairperson: MMDA",
          "- Co-Chairperson: PSA-NCR",
          "- Members: Regional Directors from 15 agencies (BLGF, DA, DBM, DENR, DepED, DILG, DOH, DOLE, DOT, DOST, DPWH, DTI, BSP, CHED, TESDA)",
          "- Representatives from PPDO, State Universities and Colleges, Private Sector",
          "- Appointed for 3-year terms with possible reappointment",
        ],
      },
      {
        title: "4. Regional Peace and Order Council (RPOC)",
        content: [
          "Coordinates peace and order initiatives in the region",
          "Monitors implementation of peace and order programs",
          "Resolves peace and order concerns at regional level",
        ],
      },
    ],
  },
};

// UPDATED RESOLUTION DATA BASED ON ALL IMAGES
const RESOLUTIONS_BY_YEAR = [
  {
    year: "Final Year 2025",
    content: [
      "RDC-NCR Resolution No. 1 - Adopting the Regional Project Monitoring and Evaluation System (RPMES) Operational Guidelines for the Regional Development Council - National Capital Region (RDC-NCR)",
      "RDC-NCR Resolution No. 2 - Endorsing the FY 2025 Budget Proposal of the Agency Regional Offices (AROs) and State Universities and Colleges (SUCs) in Metro Manila to the Department of Budget and Management (DBM) and Agency Central Offices (ACOs) for Favorable Consideration",
      "RDC-NCR Resolution No. 3 - Approving the Creation of the Regional Special Committee on Sustainable Development Goals (SDGs)",
      "RDC-NCR Resolution No. 4 - Favorably Endorsing the Supplemental Budget Proposal for New Items of Appropriations Disregarded as Conditional Implementation (CI) Under the FY 2025 General Appropriations Act (GAA) of the Department of Public Works and Highways-National Capital Region (DPWH-NCR) to the DPWH Central Office and the Department of Budget and Management (DBM)",
      "RDC-NCR Resolution No. 5 - Favorably Endorsing the Project for Learning Upgrade Support and Decentralization (PLUS-ED) of the Department of Education to the Department of Economy, Planning and Development - Investment Coordination Committee (DEPDev-ICC)",
      "RDC-NCR Resolution No. 6 - Approving and Adopting the Planning Guidelines for the Formulation of the Regional Development Plan for the National Capital Region Midterm Update 2025-2028",
      "RDC-NCR Resolution No. 7 - Endorsing the FY 2025 Supplemental Budget Proposal of the Metropolitan Manila Development Authority to the Department of Budget and Management for Economic Consideration",
      "RDC-NCR Resolution No. 8 - Endorsing the FY 2025 Supplemental Budget Proposal of the Technological University of the Philippines to the Commission on Higher Education and the Department of Budget and Management for Favorable Consideration",
      "RDC-NCR Resolution No. 9 - Favorably Endorsing the Access Expansion and Sustainability of Health Services for Universal Health Care (ACCESS UHC) Project of the Department of Health (DOH) to the Department of Economy, Planning and Development - Investment Coordination Committee (DEPDev-ICC)",
      "RDC-NCR Resolution No. 10 - Favorably Endorsing the Modern Food Inventory and Utilization with Excellence Workers (REVIVE) Project of the Department of Social Welfare and Development (DSWD) to the Department of Economy, Planning and Development - Investment Coordination Committee (DEPDev-ICC)",
      "RDC-NCR Resolution No. 11 - Approving and Adopting the Metro Manila Road Safety Action Plan 2025-2028",
      "RDC-NCR Resolution No. 12 - Approving the Appointment of the Regional Development Council for the National Capital Region (RDC-NCR) Vice-Chairperson, Members of the Executive Committee and the Sectoral Committee Chairpersons and Co-chairpersons, including its Members for Calendar Year 2025-2028",
      "RDC-NCR Resolution No. 13 - Approving Creation of the Regional Development Committee for the National Capital Region (PDM-MKKS)",
      "RDC-NCR Resolution No. 14 - Expressing Support for the Establishment of Credit Rating Fund Cooperatives and Encouraging the National Government Agencies and Micro, Small, and Medium Enterprises (MSMEs) in the National Capital Region to Support the implementation of the Program",
      "RDC-NCR Resolution No. 15 - Approving and Adopting the Sustainable Development Goal (GearUp) Plan of the National Capital Region",
      "RDC-NCR Resolution No. 16 - Approving and Adopting the Regional Development Report 2024",
    ],
  },
  {
    year: "Final Year 2024",
    content: [
      "RDC-NCR Resolution No. 1 - Approval for Endorsement of the FY 2025 Budget Proposals of the Agency Regional Offices (AROs) and State Universities and Colleges (SUCs) in Metro Manila to the Department of Budget and Management (DBM) and Agency Central Offices (ACOs)",
      "RDC-NCR Resolution No. 2 - Endorsement of Integrated Stakeholders in Institutional Volunteering as a Development Strategy for National Capital Region",
      "RDC-NCR Resolution No. 3 - Endorsement to the Bureau of Customs in Metro Manila to Provide Data Support for the Philippine Statistics Authority on the Occupational Product Accounts of Metro Manila",
      "RDC-NCR Resolution No. 4 - Favorably Endorsing the Proposed Metro Manila Bridges Project (PARISP) of the Department of Public Works and Highways to the National Economic and Development Authority - Investment Coordination Committee (NEDA-ICC)",
      "RDC-NCR Resolution No. 5 - Manifestation of Support for the Creation of the Regional Custom Development Plan for the National Capital Region (RCDP-NCR) 2023-2028",
      "RDC-NCR Resolution No. 6 - Favorably Endorsing the Pasig-Marikina River Channel Improvement Project (PMRCIP), Phase IV of the Department of Public Works and Highways (DPWH) to the National Economic and Development Authority - Investment Coordination Committee (NEDA-ICC)",
      "RDC-NCR Resolution No. 7 - Favorably Endorsing the Metro Manila Priority Bridges Seismic Improvement Project (Lambingan Bridge and Guadalupe Bridges) of the Department of Public Works and Highways (DPWH) to the National Economic and Development Authority - Investment Coordination Committee (NEDA-ICC)",
      "RDC-NCR Resolution No. 8 - Favorably Endorsing the Philippine International Exhibition Center (PIEC) Project of the Philippine Performance Authority (PPA) to the National Economic and Development Authority - Investment Coordination Committee (NEDA-ICC)",
      "RDC-NCR Resolution No. 9 - Endorsement and Adoption of Regional Development Report (RDR) 2023",
      "RDC-NCR Resolution No. 10 - Manifestation of Support for the Project Entitled 'Review and Updating of the Climate-Resilient Integrated River Basin Management and Development Master Plan (CRIBMDMP) for the Marikina River Basin'",
      "RDC-NCR Sectoral Committee on Economic and Environment Development and Infrastructure Development Resolution No. 11 - Endorsing to the Regional Development Council of the National Capital Region for Endorsement the Department of Environment and Natural Resources Funded Project Entitled 'Review and Updating of the Climate-Resilient Integrated River Basin Management and Development Master Plan (CRIBMDMP) for the Marikina River Basin'",
      "RDC-NCR Sectoral Committee on Infrastructure Development Resolution No. 12 - Favorably Endorsing the Pasig-Marikina River Channel Improvement Project (PMRCIP), Phase IV of the Department of Public Works and Highways (DPWH) to the Regional Development Council of the National Capital Region (RDC-NCR)",
    ],
  },
  {
    year: "Final Year 2023",
    content: [
      "RDC-NCR Resolution No. 1 - Approval and Adoption of the Supplemental Planning Guidelines in the Formulation of the Regional Development Plan for the National Capital Region (RDP-NCR) 2023-2028",
      "RDC-NCR Resolution No. 2 - Approval for Endorsement of the FY 2024 Budget Proposals of the Agency Regional Offices (AROs) and State Universities and Colleges (SUCs) in Metro Manila to the Department of Budget and Management (DBM) and Agency Central Offices (ACOs)",
      "RDC-NCR Resolution No. 3 - Approval and Adoption of the Regional Development Report (RDR) 2020-2022 as Input to the Formulation of the RDP-NCR 2023-2028",
      "RDC-NCR Resolution No. 4 - Approval and Adoption of the Guidelines for the Formulation of the Regional Development Investment Program for the National Capital Region (RDIP-NCR) 2023-2028",
      "RDC-NCR Resolution No. 5 - Endorsing the Adoption of RDC-NCR Resolution No. 6, Series of 2023 for Estimating Government and Private Establishments Metrics Under the Updated 2024 Philippine Standard Industrial Classification (PSIC) with 2019 Updates",
      "RDC-NCR Resolution No. 6 - Endorsing RDC-NCR Resolution 3 Series of 2023 Encouraging Data Source Agreement to Metro Manila to Provide Revenue to the PSA-NEDA for the Estimation of the Regional Accounts of NCR",
      "RDC-NCR Resolution No. 7 - Endorsing the DOST Priority Legislation Agenda",
      "RDC-NCR Resolution No. 8 - Approving the Extension of the Metro Manila Flood Management Project, Phase I of the DPWH and its MMDA for Endorsement to the NEDA-ICC",
      "RDC-NCR Resolution No. 9 - Endorsing and Adopting the Regional Development Plan for the National Capital Region (RDP-NCR) 2023-2028",
      "RDC-NCR Resolution No. 10 - Approving and Adopting the Regional Development Investment Program for the National Capital Region (RDIP-NCR) 2023-2028",
      "RDC-NCR Resolution No. 11 - Approving the Change in Scope and Cost of the Metro Manila Flood Management Project, Phase I of the Department of Public Works and Highways (DPWH) and the Metropolitan Manila Development Authority (MMDA) for Endorsement to the National Economic and Development Authority-Investment Coordination Committee (NEDA-ICC)",
      "RDC-NCR Sectoral Committee on Infrastructure Development Resolution No. 12 - Approving the Extension of the Metro Manila Flood Management Project, Phase I of the Department of Public Works and Highways (DPWH) and the Metropolitan Manila Development Authority (MMDA) for Endorsement to the National Economic and Development Authority-Investment Coordination Committee (NEDA-ICC)",
      "RDC-NCR Sectoral Committee on Infrastructure Development Resolution No. 13 - Endorsing to the Regional Development Council of the National Capital Region the Chapter on Infrastructure Development of the Regional Development Plan 2023-2028 for Favorable Consideration",
      "RDC-NCR Sectoral Committee on Economic and Environment Development Resolution No. 14 - Endorsing to the Regional Development Council of the National Capital Region the Chapter on Economic and Environment Development of the Regional Development Plan 2023-2028 for Favorable Consideration",
      "RDC-NCR Sectoral Committee on Social Development Resolution No. 15 - Endorsing to the Regional Development Council of the National Capital Region the Chapter on Social Development of the Regional Development Plan 2023-2028 for Favorable Consideration",
      "RDC-NCR Sectoral Committee on Finance and Development Administration Resolution No. 16 - Endorsing to the Regional Development Council of the National Capital Region the Chapter on Finance and Development Administration of the Regional Development Plan 2023-2028 for Favorable Consideration",
    ],
  },
  {
    year: "Final Year 2022",
    content: [
      "RDC-NCR Resolution No. 1 -   APPROVING THE APPOINTMENT OF THE REGIONAL DEVELOPMENT COUNCIL FOR THE NATIONAL CAPITAL REGION (RDC-NCR) VICE CHAIRPERSON, MEMBERS OF THE EXECUTIVE COMMITTEE AND THE SECTORAL COMMITTEE CHAIRPERSONS AND CO-CHAIRPERSONS INCLUDINGS ITS MEMBERS",
      "RDC-NCR Resolution No. 2 - SUPPORTING THE BUY LOCAL ADVOCACY OF THE DEPARTMENT OF TRADE AND INDUSTRY - NATIONAL CAPITAL REGION",
      "Ad Referendum - REQUEST FOR ENDORSEMENT VIA AD REFERENDUM THE FISCAL YEAR 2023 BUDGET PROPOSALS OF AGENCY REGIONAL OFFICES AND STATE UNIVERSITIES AND COLLEGES OF METRO MANILA TO THE DEPARTMENT OF BUDGET AND MANAGEMENT AND AGENCY CENTRAL OFFICES",
    ],
  },
  {
    year: "Final Year 2021",
    content: [
      "RDC-NCR Resolution No. 1 - Endorsing to the Department of Budget and Management (DBM) and Agency Central Offices (ACOs) the FY 2022 Budget Proposals of the Agency Regional Offices (AROs) and State Universities and Colleges (SUCs) in Metro Manila for Favorable Consideration",
      "RDC-NCR Resolution No. 2 - Approving the Creation of the Regional Research, Development, and Innovation Committee as a Special Committee of the Regional Development Council-National Capital Region",
      "RDC-NCR Resolution No. 3 - Approving the Creation of the Regional Competitiveness Program Committee (RCPC) for the National Capital Region",
      "RDC-NCR Resolution No. 4 - Endorsing to the Regional Development Council - National Capital Region Additional Tier 2 Projects of the Department of Public Works and Highways - Flood Control and Management Cluster for Inclusion in the Fiscal Year 2022 Budget Proposal of DPWH for Favorable Consideration",
      "Ad Referendum - Endorsement, via Ad Referendum, of the List of Regional Priority Courses for the Commission on Higher Education (CHED) Scholarship Programs (CSPs) and Student Financial Assistance Programs (StuFAPS)",
      "Ad Referendum - DILG-DOE Joint Memorandum Circular (JMC) No. 2020-01 Guidelines for LGUs to Facilitate the Implementation of Energy Projects",
      "Ad Referendum - Endorsing to the Regional Development Council of the National Capital Region the Philippine Fisheries and Coastal Resiliency (FISHCORE) Project of the Department of Agriculture-Bureau of Fisheries and Aquatic Resources (DA-BFAR) for Favorable Consideration",
      "Ad Referendum - Regional Committee on Devolution",
      "MMDA Resolution 21-07 - Endorsing the Technical Education and Skills Development Authority (TESDA) Supporting Innovation in Philippine Technical Vocational Education and Training System (SIPTVETS) Project to the National Economic Development Authority-Investment Coordinating Committee (ICC) for Approval",
    ],
  },
  {
    year: "Final Year 2020",
    content: [
      "RDC-NCR Resolution No. 1 - Approving the Guidelines for the Formulation of the Regional Development Investment Program for the National Capital Region (RDIP-NCR) 2017-2022",
      "RDC-NCR Resolution No. 2 - Favorably Endorsing the Additional List of Projects Under 'For Later Release' of the General Appropriations Act Fiscal Year 2020 Infrastructure Program of the Department of Public Works and Highways - National Capital Region to the Department of Budget and Management",
      "RDC-NCR Resolution No. 3 - Endorsing to the Department of Budget and Management and Agency Central Offices the FY 2021 Budget Proposals of the Agency Regional Offices and State University and Colleges in Metro Manila for Favorable Consideration",
      "Ad Referendum - Construction of North-South Harbor Bridge and Palanca-Villegas Bridge, Two (2) Priority Bridges in the City of Manila under the Ten (10) Priority Bridges Crossing Pasig Marikina River and Manggahan Floodway Bridges Construction Project",
      "Ad Referendum - UP-PGH Cancer Center Project",
    ],
  },
  {
    year: "Final Year 2019",
    content: [
      "RDC-NCR Resolution No. 1 - ENDORSING TO THE DEPARTMENT OF BUDGET AND MANAGEMENT AND AGENCY CENTRAL OFFICES THE FY 2020 BUDGET PROPOSALS OF THE AGENCY REGIONAL OFFICES AND STATE UNIVERSITY AND COLLEGES IN METRO MANILA FOR FAVORABLE CONSIDERATION",
      "RDC-NCR Resolution No. 2 - ENDORSING THE REGIONAL STATISTICAL DEVELOPMENT PROGRAM FOR NATIONAL CAPITAL REGION (rsdp) 2018-2023 PER REGIONAL STATISTICS COMMITTEE FOR THE NATIONAL CAPITAL REGION (RSC-NCR) RESOLUTION NO. 06, SERIES OF 2019",
    ],
  },
  {
    year: "Final Year 2018",
    content: [
      "RDC-NCR Resolution No. 1 - Approving for Endorsement to the Department of Budget and Management for the National Capital Region (DBM-NCR) and Agency Central Offices (ACOs) the FY 2019 Budget Proposals of the Agency Regional Offices (AROs) and State University and Colleges (SUCs) in Metro Manila with a Total Amount of PHP 286,352,323,973.39",
      "RDC-NCR Resolution No. 2 - Approving for Endorsement to the Department of Budget and Management for the National Capital Region (DBM-NCR) and Respective Agency Central Offices (ACOs) the Priority Projects as Identified in the Local Development Investment Programs (LDIP) of the Local Government Units in the National Capital Region for Possible Funding and Implementation",
      "RDC-NCR Resolution No. 3 - Approving and Adopting the Regional Development Plan of the National Capital Region (RDP-NCR) 2017-2022",
      "Advisory No. 1 - Rescheduling and Revised Presentation Requirement",
      "Advisory No. 2 - Summary of Agency Program Budget Matrix (BP Forms A & A-1), Agency Performance Measures (BP Forms B & B-1), and Presentation Materials",
    ],
  },
  {
    year: "Final Year 2017",
    content: ["RDC-NCR Resolution No. 1 - Metro Manila Subway Project"],
  },
  {
    year: "Final Year 2016",
    content: [
      "Advisory No. 1 - To: All Regional Line Agencies (RLAs) and State Universities and Colleges (SUCs) in Metro Manila Reschedule of RDC-NCR Budget Consultation for FY 2017",
      "Advisory No. 2 - To: All Local Government Units (LGUs) in Metro Manila Reschedule of RDC-NCR Budget Consultation for FY 2017",
    ],
  },
  {
    year: "Final Year 2015",
    content: [
      "RDC-NCR Resolution No. 1 - Favorably Endorsing the North-South Railway Project of the Department of Transportation and Communications (DOTC) to the National Economic Development Authority - Investment Coordinating Council (NEDA-ICC)",
      "RDC-NCR Resolution No. 2 - Favorably Endorsing the Metro Manila Bus Rapid Transit - Line 1 Project of the Department of Transportation and Communications (DOTC) to the National Economic Development Authority - Investment Coordinating Council (NEDA-ICC)",
      "RDC-NCR Resolution No. 3 - Favorably Endorsing the Metro Manila Bus Transit Management Project - Phase 1 of the Metropolitan Manila Development Authority (MMDA) for Endorsement to the National Economic Development Authority - Investment Coordinating Council (NEDA-ICC)",
      "RDC-NCR Resolution No. 4 - Favorably Endorsing the Improvement/Widening of Gen. Luis Road Project (Quirino Highway in Quezon City to MacArthur Highway in Valenzuela City) Project of the Department of Public Works and Highways (DPWH) to the National Economic and Development Authority - Investment Coordinating Council (NEDA-ICC)",
      "RDC-NCR Resolution No. 5 - Favorably Endorsing the Light Rail Transit (LRT) Line 2 West Extension Project of the Department of Transportation and Communications (DOTC) to the National Economic Development Authority - Investment Coordinating Council (NEDA-ICC)",
      "RDC-NCR Resolution No. 6 - Fully Supporting Project",
      "RDC-NCR Resolution No. 7 - Favorably Endorsing the Ninoy Aquino International Airport (NAIA) Public Private Partnership (PPP) Project of the Department of Transportation and Communications (DOTC) to the National Economic Development Authority - Investment Coordinating Council (NEDA-ICC)",
      "RDC-NCR Resolution No. 8 - Connector Metro Manila Expressway (CMMEX) Project",
      "RDC-NCR Resolution No. 9 - Bonifacio Global City to Taguig Link Road Project, Phase 1B",
      "RDC-NCR Resolution No. 10 - Valenzuela Bridges Seismic Improvement Project - Guadalupe and Lambingan Bridges",
    ],
  },
  {
    year: "Final Year 2014",
    content: [
      "RDC-NCR Resolution No. 1 - APPROVING THE CREATION OF A SUB-COMMITTEE ON SOCIAL PROTECTION UNDER THE REGIONAL DEVELOPMENT COUNCIL- SECTORAL COMMITTEE ON SOCIAL DEVELOPMENT",
      "RDC-NCR Resolution No. 2 - URGING THE NATIONAL ECONOMIC DEVELOPMENT AUHTORITY BOARD SECRETARIAT TO REFRAIN FROM EVALUATING PROJECTS WITHIN METRO MANILA WITHOUT FIRST SECURING THE APPROPRIATE ENDORSEMENT FROM THE REGIONAL DEVELOPMENT COUNCIL - NATIONAL CAPITAL REGION (RDC-NCR)",
      "RDC-NCR Resolution No. 3 - FAVORABLY ENDORSING THE AUTOMATIC FARE COLLECTION SYSTEM PROJECT  OF THE DEPARTMENT OF TRANSPORTATION AND COMMUNICATIONS (DOTC) TO THE NATIONAL ECONOMIC DEVELOPMENT AUTHORITY - INVESTMENT COORDINATING COUNCIL (NEDA-ICC)",
      "RDC-NCR Resolution No. 3 - FAVORABLY ENDORSING THE AUTOMATIC FARE COLLECTION SYSTEM PROJECT  OF THE DEPARTMENT OF TRANSPORTATION AND COMMUNICATIONS (DOTC) TO THE NATIONAL ECONOMIC DEVELOPMENT AUTHORITY - INVESTMENT COORDINATING COUNCIL (NEDA-ICC)",
      "RDC-NCR Resolution No. 5 - DEVELOPMENT OF THE INTEGRATED TRANSPORT SYSTEM (ITS) TERMINALS AT FOOD TERMINAL INCORPORATED (FTI) AND PHILIPPINE RECLAMATION AREA (PRA) UNDER PUBLIC-PRIVATE PARTNERSHIP OF THE DEPARTMENT OF TRANSPORTATION AND COMMUNICATIONS (DOTC) TO THE NATIONAL ECONOMIC DEVELOPMENT AUTHORITY - INVESTMENT COORDINATING COUNCIL (NEDA-ICC)",
      "RDC-NCR Resolution No. 6 - FAVORABLY ENDORSING THE LRT LINE 2 EAST EXTENSION OF THE DEPARTMENT OF TRANSPORTATION AND COMMUNICATIONS (DOTC)-LIGHT RAIL TRANSIT AUTHORITY (LRTA) TO THE NATIONAL ECONOMIC DEVELOPMENT AUTHORITY - INVESTMENT COORDINATING COUNCIL (NEDA-ICC)",
      "RDC-NCR Resolution No. 7 - FAVORABLY ENDORSING THE SEN. GIL PUYAT AVE. / MAKATI AVE. - PASEO DE ROXAS VEHICLE UNDERPASS PROJECT OF THE DEPARTMENT OF PUBLIC WORKS AND HIGHWAYS (DPWH) TO THE NATIONAL ECONOMIC AND DEVELOPMENT AUTHORITY - INVESTMENT COORDINATING COUNCIL (NEDA-ICC)",
      "RDC-NCR Resolution No. 8 - FAVORABLY ENDORSING THE BONIFACIO AVENUE TO ORTIGAS LINK ROAD PHASE I AND PHASE IIA PROJECT OF THE DEPARTMENT OF PUBLIC WORKS AND HIGHWAYS (DPWH) TO THE NATIONAL ECONOMIC AND DEVELOPMENT AUTHORITY - INVESTMENT COORDINATING COUNCIL (NEDA-ICC)",
      "RDC-NCR Resolution No. 9 - FAVORABLY ENDORSING THE METRO MANILA SKYWAY STAGE 3  - ADVANCE WORKS PROJECT OF THE DEPARTMENT OF TRANSPORTATION AND COMMUNICATIONS (DOTC) TO THE NATIONAL ECONOMIC DEVELOPMENT AUTHORITY - INVESTMENT COORDINATING COUNCIL (NEDA-ICC)",
      "RDC-NCR Resolution No. 10 - FAVORABLY ENDORSING THE MODERNIZATION OF PHILIPPINE ORTHOPEDIC CENTER OF THE DEPARTMENT OF HEALTH TO THE NATIONAL ECONOMIC DEVELOPMENT AUTHORITY - INVESTMENT COORDINATING COUNCIL (NEDA-ICC)",
      "RDC-NCR Resolution No. 11 - FAVORABLY ENDORSING THE SOUTH LUNA AND MCKINLEY HILL RAMPS PROJECT PHASE I OF THE BASES CONVERSION DEVELOPMENT ADMINISTRATION (BCDA) TO THE NATIONAL ECONOMIC DEVELOPMENT AUTHORITY - INVESTMENT COORDINATING COUNCIL (NEDA-ICC)",
      "RDC-NCR Resolution No. 12 - FAVORABLY ENDORSING THE METRO MANILA SKYWAY (MMS) STAGE 3 PROJECT OF THE DEPARTMENT OF TRANSPORTATION AND COMMUNICATIONS (DOTC) TO THE NATIONAL ECONOMIC AND DEVELOPMENT AUTHORITY - INVESTMENT COORDINATING COUNCIL (NEDA-ICC)",
      "RDC-NCR Resolution No. 13 - FAVORABLY ENDORSING THE C-5 / GREENMEADOWS / ACROPOLIS / INDUSTRIA AVE. INTERCHANGE COMPONENT OF THE METRO MANILA INTERCHANGE CONSTRUCTION PROJECT (MMICP), PHASE VI OF THE DEPARTMENT OF PUBLIC WORKS AND HIGHWAYS (DPWH) TO THE NATIONAL ECONOMIC AND DEVELOPMENT AUTHORITY - INVESTMENT COORDINATING COUNCIL (NEDA-ICC)",
      "RDC-NCR Resolution No. 14 - Modernization of the Dr. Jose Fabella Memorial Hospital Project",
      "RDC-NCR Resolution No. 15 - FAVORABLY ENDORSING THE EDSA / NORTH / WEST / MINDANAO AVENUE INTERCHANGE PROJECT AND THE NORTH/MINDANAO AVENUE INTERCHANGE PROJECT OF THE DEPARTMENT OF PUBLIC WORKS AND HIGHWAYS (DPWH) TO THE NATIONAL ECONOMIC AND DEVELOPMENT AUTHORITY - INVESTMENT COORDINATING COUNCIL (NEDA-ICC)",
    ],
  },
  {
    year: "Final Year 2013",
    content: [
      "RDC-NCR Resolution No. 1 - Favorably Endorsing the MRT 3 Capacity Expansion Project of the Department of Transportation and Communications (DOTC) to the National Economic Development Authority - Investment Coordinating Council (NEDA-ICC)",
      "RDC-NCR Resolution No. 2 - Favorably Endorsing the EDSA Rehabilitation Project of the Department of Public Works and Highways (DPWH) to the National Economic Development Authority - Investment Coordinating Council (NEDA-ICC)",
    ],
  },
  {
    year: "Final Year 2012",
    content: [
      "RDC-NCR Resolution No. 1 - Favorably Endorsing the Daang Hari-South Luzon Expressway (SLEX) Link Road Project of the Department of Public Works and Highways (DPWH) to the National Economic Development Authority - Investment Coordinating Council (NEDA-ICC)",
      "RDC-NCR Resolution No. 2 - Favorably Endorsing LRT Line 1 Cavite Extension Project of the Light Rail Transit Authority (LRTA) to the National Economic Development Authority - Investment Coordinating Council (NEDA-ICC)",
      "RDC-NCR Resolution No. 3 - Resolution Approving the Implementation of the LED Traffic Information Board Project by MMDA to Help Motorists and Commuters in Making Informed Decisions in Their Daily Trips/Travel Within Metro Manila",
      "RDC-NCR Resolution No. 4 - Favorably Endorsing the Metro Manila Skybridge Project of the Metropolitan Manila Development Authority (MMDA) to the National Economic Development Authority - Investment Coordinating Council (NEDA-ICC)",
      "RDC-NCR Resolution No. 5 - Favorably Endorsing the Upgrading and Rehabilitation of the Navotas Fish Port Complex to the National Economic Development Authority - Investment Coordinating Council (NEDA-ICC)",
      "RDC-NCR Resolution No. 6 - Favorably Endorsing the Run Way Project of the Empire East Land Holdings, Inc. to the National Economic Development Authority - Investment Coordinating Council (NEDA-ICC)",
      "RDC-NCR Resolution No. 7 - Favorably Endorsing the EDSA (C-4)-Taft Avenue Intersection Flyover Project of the Department of Public Works and Highways (DPWH) to the National Economic Development Authority - Investment Coordinating Council (NEDA-ICC)",
      "RDC-NCR Resolution No. 8 - Favorably Endorsing the EDSA/Roosevelt/Congressional Avenue Interchange Project of the Department of Public Works and Highways (DPWH) to the National Economic Development Authority - Investment Coordinating Council (NEDA-ICC)",
      "RDC-NCR Resolution No. 9 - Favorably Endorsing the Taguig North Sewer Network Project of the Manila Water Company Incorporated (MWCI)",
      "RDC-NCR Resolution No. 10 - Supporting the Proposal to Increase the P30,000 Tax Exemption Ceiling of Benefits of Government Employees to a Minimum of P60,000 to P80,000",
    ],
  },
  {
    year: "Final Year 2011",
    content: [
      "RDC-NCR Resolution No. 1 - Favorably Endorsing the Eastplate Inc. Ohanaip Project, a Public Private Partnership (PPP) Project of the Bases Conversion and Development Authority (BCDA) & Fort Bonifacio Development Corporation (FBDC)",
      "RDC-NCR Resolution No. 2 - Favorably Endorsing the Ortigas East Rehabilitation Project of the Manila Water Company Incorporated (MWCI)",
      "RDC-NCR Resolution No. 3 - Favorably Endorsing the SLEX Elevated Project, a Public Private Partnership (PPP) Project of the Department of Public Works and Highways (DPWH) and Metro Pacific Tollways Development Corporation (MPTDC) to the National Economic and Development Authority - Investment Coordinating Council (NEDA-ICC)",
      "RDC-NCR Resolution No. 4 - Favorably Endorsing the NLEX Expressway Project (Phase II), a Proposed Public Private Partnership (PPP) Project of the Department of Public Works and Highways (DPWH) to the National Economic and Development Authority - Investment Coordinating Council (NEDA-ICC)",
      "RDC-NCR Resolution No. 5 - Fully Supporting the Establishment of the Metro Manila Provincial Bus Axis System (MMPBAS) of the Metropolitan Manila Development Authority",
      "RDC-NCR Resolution No. 6 - Favorably Endorsing the Establishment of Northern Luzon International Cargo Terminal Complex (NLITC), the Unexpired Proposal of the Philippine Veterans Development and Housing Corporation to the National Economic Development Authority - Investment Coordinating Council (NEDA-ICC)",
      "RDC-NCR Resolution No. 7 - Favorably Endorsing the Pasig Marikina River Channel Improvement Project (PMRCIP), Phase III, of the Department of Public Works and Highways (DPWH) to the National Economic Development Authority - Investment Coordinating Council (NEDA-ICC)",
      "RDC-NCR Resolution No. 8 - Favorably Endorsing the C-5 (Ortigas Flyover) Component of the Metro Manila Expressway Project of the Department of Public Works and Highways (DPWH) to the National Economic Development Authority - Investment Coordinating Council (NEDA-ICC)",
      "RDC-NCR Resolution No. 9 - Favorably Endorsing the C-3 (R-10) Segment, a Northern Component of the Metro Manila Expressway Project of the Department of Public Works and Highways (DPWH) to the National Economic Development Authority - Investment Coordinating Council (NEDA-ICC)",
      "RDC-NCR Resolution No. 10 - Favorably Endorsing the Brace Program Building the Resilience and Awareness of Metro Manila Communities to Natural Disasters and Climate Change Impacts Through a Demonstration Program in Pasig City to the National Economic Development Authority - Investment Coordinating Council (NEDA-ICC)",
      "RDC-NCR Resolution No. 11 - Favorably Endorsing the NLEX Expressway and its Related Roads Projects, Phase I, Including La Salle Interchange Component of the Department of Public Works and Highways (DPWH)",
      "RDC-NCR Resolution No. 12 - Favorably Endorsing the C-5 / Julia Vargas Avenue Interchange of the Department of Public Works and Highways (DPWH) to the National Economic Development Authority - Investment Coordinating Council (NEDA-ICC)",
    ],
  },
  {
    year: "Final Year 2010",
    content: [
      "RDC-NCR Resolution No. 1 - Favorably Endorsing the MRT 7 Project of the Department of Transportation and Communications (DOTC) to the National Economic Development Authority - Investment Coordinating Committee",
      "RDC-NCR Resolution No. 2 - Favorably Endorsing the Metro Manila Wastewater Management Project of the Manila Water Company Incorporated (MWCI) to the National Economic Development Authority - Investment Coordinating Committee (NEDA-ICC)",
      "RDC-NCR Resolution No. 3 - Favorably Endorsing the Sewerage and Sanitation Projects of the Maynilad Water Services Incorporated (MWSI) to the National Economic Development Authority - Investment Coordinating Committee (NEDA-ICC)",
      "RDC-NCR Resolution No. 4 - FAVORABLY ENDORSING THE C3 (G. ARANETA)/QUEZON AVENUE INTERCHANGE PROJECT OF THE DEPARTMENT OF PUBLIC WORKS AND HIGHWAYS",
    ],
  },
];

// Modal Component
const CommitteeModal: React.FC<{
  committee: Committee | null;
  detailedCommittee: DetailedCommittee | null;
  onClose: () => void;
}> = ({ committee, detailedCommittee, onClose }) => {
  if (!committee) return null;

  const hasDetailedInfo = detailedCommittee && detailedCommittee.subSections;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black bg-opacity-50" onClick={onClose} />

      {/* Modal Container */}
      <div className="flex min-h-full items-center justify-center p-4">
        <div
          className={`relative w-full ${
            hasDetailedInfo ? "max-w-6xl" : "max-w-4xl"
          } bg-white rounded-2xl shadow-2xl overflow-hidden`}
        >
          {/* Modal Header with Gradient */}
          <div className={`bg-gradient-to-r ${committee.color} p-8 text-white`}>
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-4">
                <div className="w-16 h-16 bg-white/20 backdrop-blur-sm rounded-xl flex items-center justify-center text-3xl">
                  {committee.icon}
                </div>
                <div>
                  <h2 className="text-3xl font-bold">{committee.title}</h2>
                  <p className="text-white/90 mt-2">{committee.description}</p>
                </div>
              </div>
              <button
                onClick={onClose}
                className="w-10 h-10 rounded-full bg-white/20 hover:bg-white/30 flex items-center justify-center transition"
              >
                <svg
                  className="w-6 h-6"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </button>
            </div>
          </div>

          {/* Modal Content */}
          <div className="p-8 max-h-[75vh] overflow-y-auto">
            {/* Overview Section */}
            <div className="mb-8">
              <h3 className="text-xl font-bold text-slate-900 mb-4">
                Overview
              </h3>
              <p className="text-slate-700 leading-relaxed">
                {committee.content.overview}
              </p>
            </div>

            {/* For committees with detailed info (Sectoral, Special, Affiliate) */}
            {hasDetailedInfo && detailedCommittee?.subSections ? (
              <div className="space-y-8">
                {detailedCommittee.subSections.map((section, index) => (
                  <div
                    key={index}
                    className="bg-slate-50 rounded-xl p-6 border border-slate-200"
                  >
                    <h4 className="text-lg font-bold text-slate-900 mb-4">
                      {section.title}
                    </h4>
                    <div className="space-y-3">
                      {section.content.map((item, itemIndex) => {
                        const isFunction = item.startsWith("- ");
                        const isSubHeader = item.endsWith(":");

                        if (isSubHeader) {
                          return (
                            <h5
                              key={itemIndex}
                              className="font-semibold text-slate-800 mt-3"
                            >
                              {item}
                            </h5>
                          );
                        } else if (isFunction) {
                          return (
                            <div
                              key={itemIndex}
                              className="flex items-start gap-3 ml-2"
                            >
                              <div className="w-2 h-2 rounded-full bg-blue-500 mt-2 flex-shrink-0"></div>
                              <span className="text-slate-700">
                                {item.substring(2)}
                              </span>
                            </div>
                          );
                        } else {
                          return (
                            <p key={itemIndex} className="text-slate-700">
                              {item}
                            </p>
                          );
                        }
                      })}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <>
                {/* Members Section */}
                {committee.content.members.length > 0 && (
                  <div className="mb-8">
                    <h3 className="text-xl font-bold text-slate-900 mb-4">
                      Composition
                    </h3>
                    <ul className="space-y-3">
                      {committee.content.members.map((member, index) => (
                        <li key={index} className="flex items-start gap-3">
                          <div className="w-6 h-6 rounded-full bg-green-100 flex items-center justify-center flex-shrink-0 mt-1">
                            <div className="w-2 h-2 rounded-full bg-green-600"></div>
                          </div>
                          <span className="text-slate-700">{member}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </>
            )}

            {/* Action Buttons */}
            <div className="mt-8 pt-6 border-t border-slate-200 flex justify-end">
              <button
                onClick={onClose}
                className="px-6 py-3 bg-gradient-to-r from-blue-600 to-blue-700 text-white rounded-lg font-medium hover:opacity-90 transition"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default function AboutRDC() {
  const [selectedNode, setSelectedNode] = useState<string | null>(
    "chairperson",
  );
  const [selectedCommittee, setSelectedCommittee] = useState<Committee | null>(
    null,
  );
  const [selectedDetailedCommittee, setSelectedDetailedCommittee] =
    useState<DetailedCommittee | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [expandedYears, setExpandedYears] = useState<string[]>([
    "Final Year 2025",
    "Final Year 2024",
  ]);

  const handleView = (doc: LegalDocument, event: React.MouseEvent) => {
    event.preventDefault();
    event.stopPropagation();

    if (doc.url === "#") {
      alert(
        `View link for "${doc.title}" is not yet available. Please check back later.`,
      );
      return;
    }

    window.open(doc.url, "_blank", "noopener,noreferrer");
  };

  const handleCommitteeClick = (committee: Committee) => {
    setSelectedCommittee(committee);

    if (["sectoral", "special", "affiliate"].includes(committee.id)) {
      setSelectedDetailedCommittee(DETAILED_COMMITTEES[committee.id]);
    } else {
      setSelectedDetailedCommittee(null);
    }

    setIsModalOpen(true);
  };

  const closeModal = () => {
    setIsModalOpen(false);
    setTimeout(() => {
      setSelectedCommittee(null);
      setSelectedDetailedCommittee(null);
    }, 300);
  };

  const toggleYearExpansion = (year: string) => {
    setExpandedYears((prev) =>
      prev.includes(year) ? prev.filter((y) => y !== year) : [...prev, year],
    );
  };

  // Function to extract year from string
  const extractYear = (yearString: string) => {
    const match = yearString.match(/\d{4}/);
    return match ? match[0] : yearString;
  };

  // Function to determine badge color based on year
  const getYearBadgeColor = (year: string) => {
    const yearNum = parseInt(extractYear(year));
    if (yearNum >= 2023) return "from-green-500 to-emerald-600";
    if (yearNum >= 2020) return "from-blue-500 to-cyan-600";
    if (yearNum >= 2015) return "from-purple-500 to-indigo-600";
    return "from-slate-500 to-gray-600";
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white">
      {/* Hero/Header */}
      <header className="bg-gradient-to-r from-[#012a5a] via-[#0b6fb7] to-[#0d8fb3] text-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
          <div className="max-w-4xl mx-auto text-center">
            <div className="inline-block mb-4">
              <div className="w-20 h-20 bg-white/10 backdrop-blur-sm rounded-2xl flex items-center justify-center border border-white/20 mx-auto">
                <svg
                  className="w-12 h-12 text-white"
                  fill="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
                </svg>
              </div>
            </div>
            <h1 className="text-4xl md:text-5xl font-extrabold mb-4">
              About Regional Development Council – NCR
            </h1>
            <p className="text-lg text-white/90 max-w-2xl mx-auto">
              Mandates, functions, and organizational structure guiding
              sustainable development in Metro Manila
            </p>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 space-y-20">
        {/* Legal Basis Section */}
        <section>
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold text-slate-900 mb-4">
              Legal Basis & Framework
            </h2>
            <p className="text-lg text-slate-600 max-w-2xl mx-auto">
              The foundation documents that define our mandate, structure, and
              operational guidelines
            </p>
          </div>

          {/* Changed grid to 3 columns and centered */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 max-w-5xl mx-auto">
            {LEGAL_DOCUMENTS.map((doc) => (
              <div
                key={doc.id}
                className="bg-white rounded-2xl shadow-md hover:shadow-xl transition-all overflow-hidden border border-slate-100 group flex flex-col"
              >
                <div className={`h-3 bg-gradient-to-r ${doc.color}`} />

                <div className="p-6 flex-1 flex flex-col">
                  {/* Icon */}
                  <div
                    className={`w-16 h-16 bg-gradient-to-br ${doc.color} rounded-xl flex items-center justify-center text-3xl mb-4 group-hover:scale-110 transition-transform`}
                  >
                    {doc.icon}
                  </div>

                  {/* Title */}
                  <h3 className="text-lg font-bold text-slate-900 mb-3 group-hover:text-blue-600 transition">
                    {doc.title}
                  </h3>

                  {/* Description */}
                  <p className="text-sm text-slate-600 mb-4 line-clamp-4 flex-1">
                    {doc.description}
                  </p>

                  {/* File Badge and Info */}
                  <div className="flex items-center justify-between mb-4">
                    <span className="inline-block px-3 py-1 bg-red-100 text-red-700 text-xs font-semibold rounded-full">
                      {doc.fileType}
                    </span>
                    <div className="text-right">
                      {doc.fileSize && (
                        <div className="text-xs text-slate-500">
                          {doc.fileSize}
                        </div>
                      )}
                      {doc.pages && (
                        <div className="text-xs text-slate-400">
                          {doc.pages} pages
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="mt-auto flex gap-2">
                    <button
                      onClick={(e) => handleView(doc, e)}
                      className={`flex-1 px-4 py-3 text-center font-medium rounded-lg transition flex items-center justify-center gap-2 ${
                        doc.url === "#"
                          ? "bg-slate-300 text-slate-500 cursor-not-allowed"
                          : "bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 text-white hover:shadow-md"
                      }`}
                    >
                      <svg
                        className="w-4 h-4"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth="2"
                          d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                        />
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth="2"
                          d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
                        />
                      </svg>
                      View
                    </button>
                    <a
                      href={doc.url}
                      download
                      target="_blank"
                      rel="noopener noreferrer"
                      className={`flex-1 px-4 py-3 text-center font-medium rounded-lg transition ${
                        doc.url === "#"
                          ? "bg-slate-200 text-slate-400 cursor-not-allowed pointer-events-none"
                          : "bg-slate-100 hover:bg-slate-200 text-slate-700"
                      }`}
                    >
                      Download
                    </a>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Committees Section */}
        <section>
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold text-slate-900 mb-4">
              Committees
            </h2>
            <p className="text-lg text-slate-600 max-w-2xl mx-auto">
              Click on any committee to view detailed information, functions,
              and members
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-6">
            {COMMITTEES.map((committee) => (
              <button
                key={committee.id}
                onClick={() => handleCommitteeClick(committee)}
                className="bg-white rounded-2xl shadow-md hover:shadow-xl transition-all duration-300 overflow-hidden border border-slate-100 h-full flex flex-col items-center text-center p-6 hover:-translate-y-2 active:scale-95 group"
              >
                {/* Icon Container */}
                <div
                  className={`w-20 h-20 bg-gradient-to-br ${committee.color} rounded-2xl flex items-center justify-center text-4xl mb-5 group-hover:scale-110 transition-transform duration-300 shadow-lg`}
                >
                  {committee.icon}
                </div>

                {/* Title */}
                <h3 className="text-lg font-bold text-slate-900 mb-2 group-hover:text-blue-600 transition">
                  {committee.title}
                </h3>

                {/* Description */}
                <p className="text-sm text-slate-600 mb-4 line-clamp-2">
                  {committee.description}
                </p>

                {/* Click Indicator */}
                <div className="mt-auto pt-4">
                  <div className="inline-flex items-center gap-2 text-blue-600 text-sm font-medium">
                    <span>Click to View Details</span>
                    <svg
                      className="w-4 h-4 group-hover:translate-x-1 transition-transform"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth="2"
                        d="M9 5l7 7-7 7"
                      />
                    </svg>
                  </div>
                </div>

                {/* Bottom Gradient Border */}
                <div
                  className={`mt-4 w-16 h-1 bg-gradient-to-r ${committee.color} rounded-full`}
                ></div>
              </button>
            ))}
          </div>

          {/* Info Note */}
          <div className="mt-10 text-center">
            <div className="inline-flex items-center gap-2 bg-blue-50 text-blue-700 px-4 py-2 rounded-lg text-sm">
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path
                  fillRule="evenodd"
                  d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z"
                  clipRule="evenodd"
                />
              </svg>
              Click any committee icon to view comprehensive details in a popup
              window
            </div>
          </div>
        </section>

        {/* Organizational Structure */}
        <section>
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold text-slate-900 mb-4">
              RDC-NCR Organizational Structure
            </h2>
            <p className="text-lg text-slate-600 max-w-2xl mx-auto">
              Clear governance framework showing decision-making flow and
              reporting lines
            </p>
          </div>

          {/* Modern Executive Org Chart */}
          <div className="relative rounded-3xl border border-slate-200/70 bg-gradient-to-br from-white via-slate-50 to-slate-100/60 shadow-2xl p-6 md:p-10 overflow-hidden">
            <div className="pointer-events-none absolute inset-0 opacity-[0.06] bg-[radial-gradient(circle_at_1px_1px,#1f2937_1px,transparent_0)] [background-size:20px_20px]" />
            <div className="hidden md:block absolute left-1/2 top-10 bottom-10 w-px bg-gradient-to-b from-transparent via-slate-300 to-transparent" />

            <div className="relative space-y-10 md:space-y-12">
              <div className="flex justify-center">
                <div className="flex flex-col items-center">
                  <span className="h-3 w-3 rounded-full bg-blue-600 shadow ring-4 ring-white" />
                  <span className="mt-2 h-8 w-px bg-gradient-to-b from-blue-300/70 to-transparent" />
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 md:gap-10 items-stretch">
                <div
                  onClick={() => setSelectedNode("chairperson")}
                  className={`group cursor-pointer rounded-2xl border border-slate-200/70 bg-white/80 backdrop-blur px-6 py-5 shadow-sm transition-all hover:shadow-[0_18px_40px_-22px_rgba(37,99,235,0.55)] ${
                    selectedNode === "chairperson" ? "shadow-lg ring-2 ring-blue-500/60" : "hover:shadow-lg"
                  }`}
                >
                  <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Leadership</div>
                  <div className="mt-2 text-lg font-bold text-slate-900">Chairperson</div>
                  <div className="text-sm text-slate-500">NEDA Regional Director</div>
                </div>
                <div
                  onClick={() => setSelectedNode("vice-chair")}
                  className={`group cursor-pointer rounded-2xl border border-slate-200/70 bg-white/80 backdrop-blur px-6 py-5 shadow-sm transition-all hover:shadow-[0_18px_40px_-22px_rgba(37,99,235,0.55)] ${
                    selectedNode === "vice-chair" ? "shadow-lg ring-2 ring-blue-500/60" : "hover:shadow-lg"
                  }`}
                >
                  <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Leadership</div>
                  <div className="mt-2 text-lg font-bold text-slate-900">Vice-Chairperson</div>
                  <div className="text-sm text-slate-500">Designated Representative</div>
                </div>
              </div>

              <div className="flex justify-center">
                <div className="flex flex-col items-center">
                  <span className="h-3 w-3 rounded-full bg-slate-400 shadow ring-4 ring-white" />
                  <span className="mt-2 h-8 w-px bg-gradient-to-b from-slate-300/80 to-transparent" />
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6 md:gap-8 items-stretch">
                <div
                  onClick={() => setSelectedNode("secretariat")}
                  className={`cursor-pointer rounded-2xl border border-slate-200/70 bg-white/80 backdrop-blur px-5 py-4 shadow-sm transition-all hover:shadow-[0_16px_36px_-22px_rgba(15,23,42,0.45)] ${
                    selectedNode === "secretariat" ? "shadow-lg ring-2 ring-blue-500/60" : "hover:shadow-lg"
                  }`}
                >
                  <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Core Office</div>
                  <div className="mt-2 text-base font-semibold text-slate-900">Secretariat</div>
                  <div className="text-sm text-slate-500">NCR Regional Office</div>
                </div>
                <div className="rounded-2xl border border-blue-500/40 bg-gradient-to-br from-blue-600 to-blue-700 px-6 py-5 text-white shadow-lg hover:shadow-[0_20px_45px_-22px_rgba(37,99,235,0.65)] transition-shadow">
                  <div className="text-xs font-semibold uppercase tracking-wide text-white/80">Core Office</div>
                  <div className="mt-2 text-lg font-bold">Secretary</div>
                  <div className="text-sm text-white/80">Coordinating Officer</div>
                </div>
                <div
                  onClick={() => setSelectedNode("executive-committee")}
                  className={`cursor-pointer rounded-2xl border border-slate-200/70 bg-white/80 backdrop-blur px-5 py-4 shadow-sm transition-all hover:shadow-[0_16px_36px_-22px_rgba(15,23,42,0.45)] ${
                    selectedNode === "executive-committee" ? "shadow-lg ring-2 ring-blue-500/60" : "hover:shadow-lg"
                  }`}
                >
                  <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Decision Body</div>
                  <div className="mt-2 text-base font-semibold text-slate-900">Executive Committee</div>
                  <div className="text-sm text-slate-500">Core Decision Body</div>
                </div>
              </div>

              <div className="flex justify-center">
                <div className="flex flex-col items-center">
                  <span className="h-3 w-3 rounded-full bg-slate-400 shadow ring-4 ring-white" />
                  <span className="mt-2 h-8 w-px bg-gradient-to-b from-slate-300/80 to-transparent" />
                </div>
              </div>
              <div className="rounded-3xl border border-slate-200/80 bg-white/90 backdrop-blur px-6 py-6 shadow-lg">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div>
                    <div
                      onClick={() => setSelectedNode("voting-members")}
                      className={`cursor-pointer rounded-xl bg-gradient-to-r from-blue-600 to-blue-700 text-white px-4 py-3 text-center font-semibold shadow-sm transition-all hover:shadow-[0_16px_36px_-22px_rgba(37,99,235,0.55)] ${
                        selectedNode === "voting-members" ? "shadow-lg ring-2 ring-blue-400/60" : ""
                      }`}
                    >
                      Voting Members
                    </div>
                    <div className="mt-3 space-y-2 text-sm text-slate-600">
                      <div className="rounded-lg border border-slate-200/70 bg-white px-3 py-2">17 MM Mayors</div>
                      <div className="rounded-lg border border-slate-200/70 bg-white px-3 py-2">President of MMVML</div>
                      <div className="rounded-lg border border-slate-200/70 bg-white px-3 py-2">President of MMCL</div>
                    </div>
                  </div>
                  <div>
                    <div
                      onClick={() => setSelectedNode("non-voting-members")}
                      className={`cursor-pointer rounded-xl bg-gradient-to-r from-blue-600 to-blue-700 text-white px-4 py-3 text-center font-semibold shadow-sm transition-all hover:shadow-[0_16px_36px_-22px_rgba(37,99,235,0.55)] ${
                        selectedNode === "non-voting-members" ? "shadow-lg ring-2 ring-blue-400/60" : ""
                      }`}
                    >
                      Non-Voting Members
                    </div>
                    <div className="mt-3 space-y-2 text-sm text-slate-600">
                      <div className="rounded-lg border border-slate-200/70 bg-white px-3 py-2">Secretary/Head of Agency</div>
                      <div className="rounded-lg border border-slate-200/70 bg-white px-3 py-2">Regional Directors (DOF, DOTI, DICT, etc.)</div>
                      <div className="rounded-lg border border-slate-200/70 bg-white px-3 py-2">PSO/NGO Representatives</div>
                    </div>
                  </div>
                </div>
                <div className="mt-6 border-t border-dashed border-slate-300 pt-4 text-center">
                  <div className="rounded-xl bg-slate-800 text-white px-4 py-3 font-semibold">
                    Designation of Special Non-Voting Members (SNVMs)
                  </div>
                  <div className="mt-2 text-xs text-slate-500">
                    Members of House of Representatives, NEDA Central Office, Other Agencies
                  </div>
                </div>
              </div>

              <div className="flex justify-center">
                <div className="flex flex-col items-center">
                  <span className="h-3 w-3 rounded-full bg-slate-400 shadow ring-4 ring-white" />
                  <span className="mt-2 h-8 w-px bg-gradient-to-b from-slate-300/80 to-transparent" />
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
                <div
                  onClick={() => setSelectedNode("sectoral-committees")}
                  className={`cursor-pointer rounded-2xl border border-amber-200/60 bg-gradient-to-br from-amber-100 to-amber-200/60 px-5 py-4 shadow-sm transition-all hover:shadow-[0_16px_36px_-22px_rgba(245,158,11,0.45)] ${
                    selectedNode === "sectoral-committees" ? "shadow-lg ring-2 ring-amber-400/60" : "hover:shadow-lg"
                  }`}
                >
                  <div className="text-xs font-semibold uppercase tracking-wide text-amber-700">Committees</div>
                  <div className="mt-2 text-base font-semibold text-slate-900">Sectoral Committees</div>
                  <div className="mt-3 space-y-2 text-xs text-amber-900/80">
                    <div className="rounded-lg bg-white/80 px-3 py-2">Economic & Environment</div>
                    <div className="rounded-lg bg-white/80 px-3 py-2">Finance & Dev Admin</div>
                    <div className="rounded-lg bg-white/80 px-3 py-2">Infrastructure</div>
                    <div className="rounded-lg bg-white/80 px-3 py-2">Social Development</div>
                  </div>
                </div>

                <div
                  onClick={() => setSelectedNode("special-committees")}
                  className={`cursor-pointer rounded-2xl border border-blue-200/60 bg-gradient-to-br from-blue-50 to-blue-100/60 px-5 py-4 shadow-sm transition-all hover:shadow-[0_16px_36px_-22px_rgba(37,99,235,0.45)] ${
                    selectedNode === "special-committees" ? "shadow-lg ring-2 ring-blue-400/60" : "hover:shadow-lg"
                  }`}
                >
                  <div className="text-xs font-semibold uppercase tracking-wide text-blue-700">Committees</div>
                  <div className="mt-2 text-base font-semibold text-slate-900">Special Committees</div>
                  <div className="mt-3 space-y-2 text-xs text-blue-900/80">
                    <div className="rounded-lg bg-white/80 px-3 py-2">Project Monitoring (RPMES)</div>
                    <div className="rounded-lg bg-white/80 px-3 py-2">Land Use (RLUC)</div>
                    <div className="rounded-lg bg-white/80 px-3 py-2">Research & Innovation</div>
                    <div className="rounded-lg bg-white/80 px-3 py-2">Dev Committees</div>
                  </div>
                </div>

                <div
                  onClick={() => setSelectedNode("affiliate-committees")}
                  className={`cursor-pointer rounded-2xl border border-indigo-200/60 bg-gradient-to-br from-indigo-50 to-indigo-100/60 px-5 py-4 shadow-sm transition-all hover:shadow-[0_16px_36px_-22px_rgba(79,70,229,0.45)] ${
                    selectedNode === "affiliate-committees" ? "shadow-lg ring-2 ring-indigo-400/60" : "hover:shadow-lg"
                  }`}
                >
                  <div className="text-xs font-semibold uppercase tracking-wide text-indigo-700">Committees</div>
                  <div className="mt-2 text-base font-semibold text-slate-900">Affiliate Committees</div>
                  <div className="mt-3 space-y-2 text-xs text-indigo-900/80">
                    <div className="rounded-lg bg-white/80 px-3 py-2">Welfare of Children (RCWC)</div>
                    <div className="rounded-lg bg-white/80 px-3 py-2">SME Development (RSMEDC)</div>
                    <div className="rounded-lg bg-white/80 px-3 py-2">Statistical Committee (RSC)</div>
                    <div className="rounded-lg bg-white/80 px-3 py-2">Peace & Order (RPOC)</div>
                  </div>
                </div>

                <div className="rounded-2xl border border-slate-200/70 bg-white/80 backdrop-blur px-5 py-4 shadow-sm hover:shadow-[0_16px_36px_-22px_rgba(15,23,42,0.35)] transition-all">
                  <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Advisory</div>
                  <div className="mt-2 text-base font-semibold text-slate-900">Advisory Committee</div>
                  <div className="mt-3 rounded-lg bg-slate-100 px-3 py-2 text-xs text-slate-600">
                    Expert Consultation Body
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* RESOLUTION SECTION - Updated with all accurate data */}
        <section className="mt-16 pt-8 border-t-2 border-slate-200">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold text-slate-900 mb-4">
              RDC-NCR Resolutions Archive
            </h2>
            <p className="text-lg text-slate-600 max-w-2xl mx-auto">
              Complete historical record of all RDC-NCR resolutions from 2010 to
              present
            </p>
          </div>

          <div className="bg-white rounded-3xl shadow-xl p-8 border border-slate-200">
            {/* Legend/Explanation */}
            <div className="mt-8 pt-6 border-t border-slate-200">
              <h4 className="font-semibold text-slate-900 mb-4">
                Document Type Legend
              </h4>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 bg-blue-600 rounded-full"></div>
                  <span className="text-sm text-slate-600">RDC Resolution</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 bg-amber-600 rounded-full"></div>
                  <span className="text-sm text-slate-600">
                    Advisory/Referendum
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 bg-purple-600 rounded-full"></div>
                  <span className="text-sm text-slate-600">
                    MMDA Resolution
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 bg-emerald-600 rounded-full"></div>
                  <span className="text-sm text-slate-600">
                    Sectoral Committee
                  </span>
                </div>
              </div>
            </div>

            {/* Yearly Resolution Accordion */}
            <div className="space-y-4">
              {RESOLUTIONS_BY_YEAR.map((yearData, index) => (
                <div
                  key={index}
                  className="border border-slate-200 rounded-2xl overflow-hidden hover:border-blue-300 transition-colors"
                >
                  {/* Year Header */}
                  <button
                    onClick={() => toggleYearExpansion(yearData.year)}
                    className={`w-full flex items-center justify-between p-6 text-left ${
                      expandedYears.includes(yearData.year)
                        ? "bg-gradient-to-r from-blue-50 to-indigo-50"
                        : "bg-slate-50 hover:bg-slate-100"
                    } transition-all duration-300`}
                  >
                    <div className="flex items-center gap-4">
                      <div
                        className={`w-14 h-14 bg-gradient-to-br ${getYearBadgeColor(
                          yearData.year,
                        )} rounded-xl flex items-center justify-center text-white font-bold`}
                      >
                        {extractYear(yearData.year)}
                      </div>
                      <div className="text-left">
                        <h3 className="text-xl font-bold text-slate-900">
                          {yearData.year}
                        </h3>
                        <p className="text-sm text-slate-600">
                          {yearData.content.length > 0
                            ? `${yearData.content.length} resolution${
                                yearData.content.length !== 1 ? "s" : ""
                              }`
                            : "No resolutions available"}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-4">
                      {yearData.content.length > 0 && (
                        <span
                          className={`px-3 py-1 rounded-full text-xs font-medium ${
                            yearData.content.length > 10
                              ? "bg-green-100 text-green-800"
                              : yearData.content.length > 5
                                ? "bg-blue-100 text-blue-800"
                                : "bg-slate-100 text-slate-800"
                          }`}
                        >
                          {yearData.content.length} items
                        </span>
                      )}
                      <svg
                        className={`w-6 h-6 text-blue-600 transform transition-transform duration-300 ${
                          expandedYears.includes(yearData.year)
                            ? "rotate-180"
                            : ""
                        }`}
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth="2"
                          d="M19 9l-7 7-7-7"
                        />
                      </svg>
                    </div>
                  </button>

                  {/* Content Area */}
                  {expandedYears.includes(yearData.year) &&
                    yearData.content.length > 0 && (
                      <div className="p-6 border-t border-slate-200 bg-white animate-fadeIn">
                        <div className="space-y-4">
                          {yearData.content.map((resolution, resIndex) => {
                            const isAdvisory =
                              resolution.includes("Advisory") ||
                              resolution.includes("Ad Referendum");
                            const isMMDA = resolution.includes("MMDA");
                            const isSectoral =
                              resolution.includes("Sectoral Committee");

                            return (
                              <div
                                key={resIndex}
                                className={`rounded-xl p-5 hover:shadow-md transition-all duration-200 ${
                                  isAdvisory
                                    ? "bg-amber-50 border border-amber-200 hover:bg-amber-100"
                                    : isMMDA
                                      ? "bg-purple-50 border border-purple-200 hover:bg-purple-100"
                                      : isSectoral
                                        ? "bg-emerald-50 border border-emerald-200 hover:bg-emerald-100"
                                        : "bg-slate-50 border border-slate-200 hover:bg-blue-50"
                                }`}
                              >
                                <div className="flex items-start gap-4">
                                  <div
                                    className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 mt-1 ${
                                      isAdvisory
                                        ? "bg-amber-100"
                                        : isMMDA
                                          ? "bg-purple-100"
                                          : isSectoral
                                            ? "bg-emerald-100"
                                            : "bg-blue-100"
                                    }`}
                                  >
                                    <div
                                      className={`w-3 h-3 rounded-full ${
                                        isAdvisory
                                          ? "bg-amber-600"
                                          : isMMDA
                                            ? "bg-purple-600"
                                            : isSectoral
                                              ? "bg-emerald-600"
                                              : "bg-blue-600"
                                      }`}
                                    ></div>
                                  </div>
                                  <div className="flex-1">
                                    <p className="text-slate-800 leading-relaxed">
                                      {resolution}
                                    </p>
                                    <div className="mt-3 flex flex-wrap items-center gap-2">
                                      <span
                                        className={`inline-block px-3 py-1 text-xs font-semibold rounded-full ${
                                          isAdvisory
                                            ? "bg-amber-100 text-amber-700"
                                            : isMMDA
                                              ? "bg-purple-100 text-purple-700"
                                              : isSectoral
                                                ? "bg-emerald-100 text-emerald-700"
                                                : "bg-blue-100 text-blue-700"
                                        }`}
                                      >
                                        {isAdvisory
                                          ? "Advisory"
                                          : isMMDA
                                            ? "MMDA Resolution"
                                            : isSectoral
                                              ? "Sectoral Committee"
                                              : "RDC Resolution"}
                                      </span>
                                      <span className="text-xs text-slate-500">
                                        Year: {extractYear(yearData.year)}
                                      </span>
                                      {resolution.includes("Endorsing") && (
                                        <span className="text-xs text-green-600 bg-green-50 px-2 py-1 rounded">
                                          ✓ Endorsement
                                        </span>
                                      )}
                                      {resolution.includes("Approving") && (
                                        <span className="text-xs text-blue-600 bg-blue-50 px-2 py-1 rounded">
                                          ✓ Approval
                                        </span>
                                      )}
                                    </div>
                                  </div>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}

                  {/* Empty State */}
                  {expandedYears.includes(yearData.year) &&
                    yearData.content.length === 0 && (
                      <div className="p-8 border-t border-slate-200 bg-white text-center">
                        <div className="max-w-md mx-auto">
                          <div className="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-4">
                            <svg
                              className="w-8 h-8 text-slate-400"
                              fill="none"
                              stroke="currentColor"
                              viewBox="0 0 24 24"
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth="1.5"
                                d="M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 002.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 00-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 00.75-.75 2.25 2.25 0 00-.1-.664m-5.8 0A2.251 2.251 0 0113.5 2.25H15c1.012 0 1.867.668 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m0 0H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375c0-.621-.504-1.125-1.125-1.125H8.25zM6.75 12h.008v.008H6.75V12zm0 3h.008v.008H6.75V15zm0 3h.008v.008H6.75V18z"
                              />
                            </svg>
                          </div>
                          <h4 className="text-lg font-semibold text-slate-700 mb-2">
                            No Resolutions Recorded
                          </h4>
                          <p className="text-slate-500">
                            No official resolutions were documented for{" "}
                            {yearData.year}.
                          </p>
                        </div>
                      </div>
                    )}
                </div>
              ))}
            </div>

            {/* Stats Summary */}
            <div className="mb-10 p-6 bg-gradient-to-r from-blue-50 to-indigo-50 rounded-2xl">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="text-center">
                  <div className="text-3xl font-bold text-blue-700">
                    {RESOLUTIONS_BY_YEAR.length}
                  </div>
                  <div className="text-sm text-slate-600">Years Covered</div>
                </div>
                <div className="text-center">
                  <div className="text-3xl font-bold text-blue-700">
                    {RESOLUTIONS_BY_YEAR.reduce(
                      (acc, year) => acc + year.content.length,
                      0,
                    )}
                  </div>
                  <div className="text-sm text-slate-600">
                    Total Resolutions
                  </div>
                </div>
                <div className="text-center">
                  <div className="text-3xl font-bold text-blue-700">
                    {Math.max(
                      ...RESOLUTIONS_BY_YEAR.map((y) => y.content.length),
                    )}
                  </div>
                  <div className="text-sm text-slate-600">Most in a Year</div>
                </div>
                <div className="text-center">
                  <div className="text-3xl font-bold text-blue-700">
                    2010-2025
                  </div>
                  <div className="text-sm text-slate-600">Date Range</div>
                </div>
              </div>
            </div>

            {/* Summary Stats */}
            <div className="mt-8 p-6 bg-slate-50 rounded-2xl">
              <h4 className="font-semibold text-slate-900 mb-3">
                Resolution Categories Summary
              </h4>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="text-center p-3 bg-white rounded-lg">
                  <div className="text-lg font-bold text-blue-600">Budget</div>
                  <div className="text-sm text-slate-600">
                    Budget Endorsements
                  </div>
                </div>
                <div className="text-center p-3 bg-white rounded-lg">
                  <div className="text-lg font-bold text-green-600">
                    Infrastructure
                  </div>
                  <div className="text-sm text-slate-600">
                    Project Endorsements
                  </div>
                </div>
                <div className="text-center p-3 bg-white rounded-lg">
                  <div className="text-lg font-bold text-purple-600">
                    Policy
                  </div>
                  <div className="text-sm text-slate-600">Policy Approvals</div>
                </div>
                <div className="text-center p-3 bg-white rounded-lg">
                  <div className="text-lg font-bold text-amber-600">
                    Administrative
                  </div>
                  <div className="text-sm text-slate-600">
                    Committee Creations
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* Modal Popup */}
      {isModalOpen && (
        <CommitteeModal
          committee={selectedCommittee}
          detailedCommittee={selectedDetailedCommittee}
          onClose={closeModal}
        />
      )}
    </div>
  );
}

