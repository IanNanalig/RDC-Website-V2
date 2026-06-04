import React from "react";

type Props = {
  profileData: Record<string, any> | null | undefined;
};

const value = (v: any) => {
  if (v === null || v === undefined || v === "") return "-";
  if (Array.isArray(v)) return v.length ? v.join(", ") : "-";
  if (typeof v === "object") return JSON.stringify(v, null, 2);
  return String(v);
};

const joined = (v: any) => (Array.isArray(v) ? (v.length ? v.join(", ") : "-") : value(v));
const has = (arr: any, item: string) => Array.isArray(arr) && arr.includes(item);
const Check = ({ on }: { on: boolean }) => <span className="inline-block w-4">{on ? "[x]" : "[ ]"}</span>;

const ProjectProfileReadOnly: React.FC<Props> = ({ profileData }) => {
  if (!profileData) {
    return <div className="text-sm text-gray-500">No full profile data submitted.</div>;
  }

  const costRows = Array.isArray(profileData.projectCostRows) ? profileData.projectCostRows : [];
  const pipRows = Array.isArray(profileData.pipBudgetRows) ? profileData.pipBudgetRows : [];
  const provRows = Array.isArray(profileData.provincialRows) ? profileData.provincialRows : [];
  const otherPdp = Array.isArray(profileData.otherPdpChapters)
    ? profileData.otherPdpChapters.join(", ")
    : value(profileData.otherPdpChapters);

  return (
    <div className="space-y-6 text-sm print:text-[11px] print-token">
      <section className="border border-gray-300 rounded p-3 print:border-black print:rounded-none">
        <p className="text-[10px] uppercase tracking-wide text-center font-semibold">
          UPDATING OF THE PUBLIC INVESTMENT PROGRAM (PIP) 2023-2028 AND FORMULATION OF THE THREE-YEAR ROLLING INFRASTRUCTURE PROGRAM (TRIP) FOR FYs 2027-2029
        </p>
        <p className="text-center font-bold mt-1">PROGRAM/PROJECT PROFILE</p>
      </section>

      <section className="border border-gray-300 rounded p-3 print:border-black print:rounded-none">
        <h4 className="font-semibold mb-2">PROJECT TITLE [1]</h4>
        <p className="mb-2">{value(profileData.projectTitle)}</p>
        <h4 className="font-semibold mb-2">MMDA OFFICE/ UNIT-IN-CHARGE</h4>
        <p className="mb-2">{value(profileData.officeUnit)}</p>
        <h4 className="font-semibold mb-2">PROGRAM / PROJECT CLASSIFICATION</h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          <div><span className="text-gray-500">Is it a Program or a Project? [2][4]: </span>{value(profileData.programOrProject)}</div>
          <div><span className="text-gray-500">Is it a regular program? [3]: </span>{value(profileData.isRegularProgram)}</div>
          <div><span className="text-gray-500">Part/subcomponent/subproject of Program? [5]: </span>{value(profileData.isSubcomponent)}</div>
          <div><span className="text-gray-500">Parent Program Title [6]: </span>{value(profileData.parentProgramTitle)}</div>
          <div><span className="text-gray-500">Parent Program PIP Code: </span>{value(profileData.parentProgramPipCode)}</div>
          <div><span className="text-gray-500">Sub Program [7]: </span>{value(profileData.subProgram)}</div>
          <div><span className="text-gray-500">Convergence Program (PCB)? [8]: </span>{value(profileData.isConvergenceProgram)}</div>
        </div>
      </section>

      <section className="border border-gray-300 rounded p-3 print:border-black print:rounded-none">
        <h4 className="font-semibold mb-2">BASIS FOR IMPLEMENTATION [9]</h4>
        <div className="grid md:grid-cols-2 gap-x-4 gap-y-1 mb-2 text-[11px]">
          <div><Check on={has(profileData.basisSelections, "General Appropriations Act (GAA)")} /> General Appropriations Act (GAA)</div>
          <div><Check on={has(profileData.basisSelections, "National Expenditure Program (NEP)")} /> National Expenditure Program (NEP)</div>
          <div><Check on={has(profileData.basisSelections, "Multi-Year Obligational Authority (MYOA)")} /> MYOA</div>
          <div><Check on={has(profileData.basisSelections, "Multi-Year Contracting Authority (MYCA)")} /> MYCA</div>
          <div><Check on={has(profileData.basisSelections, "Existing masterplan/sector studies/procurement plan")} /> Existing masterplan/sector studies</div>
          <div><Check on={has(profileData.basisSelections, "List of RDC-endorsed programs/projects")} /> RDC-endorsed programs/projects</div>
          <div><Check on={has(profileData.basisSelections, "Signed Agreements/International Commitments")} /> Signed Agreements/International Commitments</div>
          <div><Check on={has(profileData.basisSelections, "Regular program (e.g. PAMANA/HFEP)")} /> Regular program</div>
          <div><Check on={has(profileData.basisSelections, "List of ARNIPAPs from RNIPD")} /> ARNIPAPs from RNIPD</div>
          <div><Check on={has(profileData.basisSelections, "Other existing laws/rules/regulations")} /> Other laws/rules/regulations</div>
        </div>
        <div className="space-y-1">
          <p className="whitespace-pre-wrap"><span className="text-gray-500">Basis for Implementation: </span>{value(profileData.basisForImplementation)}</p>
          <p className="whitespace-pre-wrap"><span className="text-gray-500">Checklist: </span>{joined(profileData.basisSelections)}</p>
          <p className="whitespace-pre-wrap"><span className="text-gray-500">Signed Agreements/International Commitments [10]: </span>{value(profileData.remarks)}</p>
          <p className="whitespace-pre-wrap mt-2"><span className="font-semibold">PROJECT OBJECTIVE:</span> {value(profileData.objective)}</p>
          <p className="whitespace-pre-wrap mt-2"><span className="font-semibold">PROJECT DESCRIPTION:</span> {value(profileData.description)}</p>
          <p className="mt-2"><span className="font-semibold">IMPLEMENTING AGENCY:</span> {value(profileData.implementingAgency)}</p>
          <p><span className="text-gray-500">Start of Project Implementation [11]: </span>{value(profileData.startYear)} <span className="text-gray-500 ml-4">Year of Project Completion [12]: </span>{value(profileData.completionYear)}</p>
        </div>
      </section>
      <section className="border border-gray-300 rounded p-3 print:border-black print:rounded-none">
        <h4 className="font-semibold mb-2">SPATIAL COVERAGE - By Cost/Investment [13]</h4>
        <p className="text-[11px]">
          <Check on={String(profileData.coverageByCostType).toLowerCase().includes("nationwide")} /> Nationwide
          <span className="mx-2" />
          <Check on={String(profileData.coverageByCostType).toLowerCase().includes("interregional")} /> Interregional
          <span className="mx-2" />
          <Check on={String(profileData.coverageByCostType).toLowerCase().includes("region")} /> Region-Specific
          <span className="mx-2" />
          <Check on={String(profileData.coverageByCostType).toLowerCase().includes("abroad")} /> Abroad
        </p>
        <p className="whitespace-pre-wrap">{value(profileData.spatialCoverageByCost)}</p>
        <h4 className="font-semibold mt-3 mb-2">SPATIAL COVERAGE - By Impact [14][15][16][17]</h4>
        <p className="text-[11px]">
          <Check on={String(profileData.coverageByImpactType).toLowerCase().includes("nationwide")} /> Nationwide
          <span className="mx-2" />
          <Check on={String(profileData.coverageByImpactType).toLowerCase().includes("interregional")} /> Interregional
          <span className="mx-2" />
          <Check on={String(profileData.coverageByImpactType).toLowerCase().includes("region")} /> Region-Specific
          <span className="mx-2" />
          <Check on={String(profileData.coverageByImpactType).toLowerCase().includes("abroad")} /> Abroad
        </p>
        <p className="whitespace-pre-wrap">{value(profileData.spatialCoverageByImpact)}</p>
        <h4 className="font-semibold mt-3 mb-2">INCLUSION IN PROGRAMMING DOCUMENT [18][19][20][21]</h4>
        <p className="whitespace-pre-wrap">{value(profileData.inclusionProgramming)}</p>
        <p className="whitespace-pre-wrap"><span className="text-gray-500">PIP: </span>{value(profileData.inclusionPip)} | <span className="text-gray-500">CIP: </span>{value(profileData.inclusionCip)} | <span className="text-gray-500">TRIP: </span>{value(profileData.inclusionTrip)}</p>
        <p className="whitespace-pre-wrap"><span className="text-gray-500">ARNIPAP: </span>{value(profileData.inclusionArnipap)} | <span className="text-gray-500">R&D P/P: </span>{value(profileData.inclusionRdProgram)} | <span className="text-gray-500">Included in RDIP: </span>{value(profileData.includedInRdip)} | <span className="text-gray-500">Requires RDC Endorsement: </span>{value(profileData.requiresRdcEndorsement)}</p>
        <h4 className="font-semibold mt-3 mb-2">PHYSICAL AND FINANCIAL STATUS [22][23]</h4>
        <p className="whitespace-pre-wrap">{value(profileData.physicalFinancialStatus)}</p>
        <p className="whitespace-pre-wrap"><span className="text-gray-500">Category: </span>{value(profileData.categoryStatus)} | <span className="text-gray-500">Readiness Level: </span>{value(profileData.implementationReadinessLevel)}</p>
        <p className="whitespace-pre-wrap"><span className="text-gray-500">Implementation Risk [24] / Mitigation Strategies [25]: </span>{value(profileData.riskAndMitigation)}</p>
        <p><span className="text-gray-500">PAP Code [26]: </span>{value(profileData.papCode)} <span className="text-gray-500 ml-4">Update as of [28]: </span>{value(profileData.updatesAsOf)}</p>
      </section>

      <section className="border border-gray-300 rounded p-3 print:border-black print:rounded-none">
        <h4 className="font-semibold mb-2">FUNDING SOURCES AND MODE OF IMPLEMENTATION</h4>
        <div className="grid md:grid-cols-2 gap-x-4 gap-y-1 mb-2 text-[11px]">
          <div><Check on={has(profileData.fundingSources, "NG")} /> NG</div>
          <div><Check on={has(profileData.fundingSources, "LGU Counterpart")} /> LGU Counterpart</div>
          <div><Check on={has(profileData.fundingSources, "ODA Loan")} /> ODA Loan</div>
          <div><Check on={has(profileData.fundingSources, "ODA Grant")} /> ODA Grant</div>
          <div><Check on={has(profileData.fundingSources, "GOCC/GFIs")} /> GOCC/GFIs</div>
          <div><Check on={has(profileData.fundingSources, "Private Sector")} /> Private Sector</div>
          <div><Check on={has(profileData.fundingSources, "Others")} /> Others</div>
        </div>
        <p className="whitespace-pre-wrap"><span className="text-gray-500">Funding Sources and Mode: </span>{value(profileData.fundingSourcesAndMode)}</p>
        <p className="whitespace-pre-wrap"><span className="text-gray-500">Funding Sources: </span>{joined(profileData.fundingSources)}</p>
        <p className="whitespace-pre-wrap"><span className="text-gray-500">Main Funding Sources: </span>{joined(profileData.mainFundingSources)}</p>
        <p className="whitespace-pre-wrap"><span className="text-gray-500">Mode of Implementation: </span>{joined(profileData.implementationModes)}</p>
        <p className="whitespace-pre-wrap"><span className="text-gray-500">PROJECT COST (In Exact Amount in PHP): </span>{value(profileData.totalProjectCost)}</p>
      </section>

      {costRows.length > 0 && (
        <section className="print:break-inside-avoid">
          <h4 className="font-semibold text-sm mb-2">PROJECT COST MATRIX [29][30]</h4>
          <div className="overflow-x-auto border rounded print:border-black print:rounded-none">
            <table className="min-w-full text-xs print-fixed-table">
              <thead className="bg-gray-50 print:bg-transparent">
                <tr>
                  <th className="px-2 py-1 text-left border-b border-gray-300 print:border-black">Source</th>
                  <th className="px-2 py-1 text-left border-b border-gray-300 print:border-black">2022 and Prior</th>
                  <th className="px-2 py-1 text-left border-b border-gray-300 print:border-black">2023</th>
                  <th className="px-2 py-1 text-left border-b border-gray-300 print:border-black">2024</th>
                  <th className="px-2 py-1 text-left border-b border-gray-300 print:border-black">2025</th>
                  <th className="px-2 py-1 text-left border-b border-gray-300 print:border-black">2026</th>
                  <th className="px-2 py-1 text-left border-b border-gray-300 print:border-black">2027</th>
                  <th className="px-2 py-1 text-left border-b border-gray-300 print:border-black">2028</th>
                  <th className="px-2 py-1 text-left border-b border-gray-300 print:border-black">2029</th>
                  <th className="px-2 py-1 text-left border-b border-gray-300 print:border-black">Continuing Years</th>
                  <th className="px-2 py-1 text-left border-b border-gray-300 print:border-black">Overall</th>
                </tr>
              </thead>
              <tbody>
                {costRows.map((r: any, idx: number) => (
                  <tr key={idx} className="border-t border-gray-300 print:border-black">
                    <td className="px-2 py-1">{value(r.source)}</td>
                    <td className="px-2 py-1">-</td>
                    <td className="px-2 py-1">-</td>
                    <td className="px-2 py-1">-</td>
                    <td className="px-2 py-1">{value(r.y2025)}</td>
                    <td className="px-2 py-1">{value(r.y2026)}</td>
                    <td className="px-2 py-1">{value(r.y2027)}</td>
                    <td className="px-2 py-1">-</td>
                    <td className="px-2 py-1">-</td>
                    <td className="px-2 py-1">-</td>
                    <td className="px-2 py-1">{value(r.overall)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {pipRows.length > 0 && (
        <section className="print:break-inside-avoid">
          <h4 className="font-semibold text-sm mb-2">PIP-Budget Tracker [31]</h4>
          <div className="overflow-x-auto border rounded print:border-black print:rounded-none">
            <table className="min-w-full text-xs print-fixed-table">
              <thead className="bg-gray-50 print:bg-transparent">
                <tr>
                  <th className="px-2 py-1 text-left border-b border-gray-300 print:border-black">Year</th>
                  <th className="px-2 py-1 text-left border-b border-gray-300 print:border-black">OSBPS</th>
                  <th className="px-2 py-1 text-left border-b border-gray-300 print:border-black">NEP</th>
                  <th className="px-2 py-1 text-left border-b border-gray-300 print:border-black">GAA</th>
                </tr>
              </thead>
              <tbody>
                {["2025", "2026", "2027", "2028", "2029"].map((year, idx) => {
                  const r = pipRows.find((x: any) => String(x.year) === year) || {};
                  return (
                  <tr key={idx} className="border-t border-gray-300 print:border-black">
                    <td className="px-2 py-1">{year}</td>
                    <td className="px-2 py-1">{value(r.osbps)}</td>
                    <td className="px-2 py-1">{value(r.nep)}</td>
                    <td className="px-2 py-1">{value(r.gaa)}</td>
                  </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {provRows.length > 0 && (
        <section className="print:break-inside-avoid">
          <h4 className="font-semibold text-sm mb-2">PROVINCIAL/ DISTRICT BREAKDOWN</h4>
          <div className="overflow-x-auto border rounded print:border-black print:rounded-none">
            <table className="min-w-full text-xs print-fixed-table">
              <thead className="bg-gray-50 print:bg-transparent">
                <tr>
                  <th className="px-2 py-1 text-left border-b border-gray-300 print:border-black">Province/District</th>
                  <th className="px-2 py-1 text-left border-b border-gray-300 print:border-black">2022 and Prior</th>
                  <th className="px-2 py-1 text-left border-b border-gray-300 print:border-black">2023</th>
                  <th className="px-2 py-1 text-left border-b border-gray-300 print:border-black">2024</th>
                  <th className="px-2 py-1 text-left border-b border-gray-300 print:border-black">2025</th>
                  <th className="px-2 py-1 text-left border-b border-gray-300 print:border-black">2026</th>
                  <th className="px-2 py-1 text-left border-b border-gray-300 print:border-black">2027</th>
                  <th className="px-2 py-1 text-left border-b border-gray-300 print:border-black">2028</th>
                  <th className="px-2 py-1 text-left border-b border-gray-300 print:border-black">2029</th>
                  <th className="px-2 py-1 text-left border-b border-gray-300 print:border-black">Continuing Years</th>
                  <th className="px-2 py-1 text-left border-b border-gray-300 print:border-black">Overall</th>
                </tr>
              </thead>
              <tbody>
                {provRows.map((r: any, idx: number) => (
                  <tr key={idx} className="border-t border-gray-300 print:border-black">
                    <td className="px-2 py-1">{value(r.province)}</td>
                    <td className="px-2 py-1">-</td>
                    <td className="px-2 py-1">-</td>
                    <td className="px-2 py-1">-</td>
                    <td className="px-2 py-1">{value(r.y2025)}</td>
                    <td className="px-2 py-1">{value(r.y2026)}</td>
                    <td className="px-2 py-1">-</td>
                    <td className="px-2 py-1">-</td>
                    <td className="px-2 py-1">-</td>
                    <td className="px-2 py-1">-</td>
                    <td className="px-2 py-1">{value(r.overall)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section className="space-y-1 border border-gray-300 rounded p-3 print:border-black print:rounded-none">
        <h4 className="font-semibold">LEVEL OF APPROVAL</h4>
        <p className="text-[11px]">
          <Check on={String(profileData.levelOfApproval).toLowerCase().includes("icc")} /> Will require ICC/ED Council Approval
          <span className="mx-2" />
          <Check on={String(profileData.levelOfApproval).toLowerCase().includes("not")} /> Not Applicable
        </p>
        <p>{value(profileData.levelOfApproval)}</p>
        <h4 className="font-semibold mt-3">PHILIPPINE DEVELOPMENT PLAN (PDP) CHAPTERS</h4>
        <p><span className="text-gray-500">MAIN PDP CHAPTER: </span>{value(profileData.mainPdpChapter)}</p>
        <p className="whitespace-pre-wrap"><span className="text-gray-500">OTHER PDP CHAPTER(S) [32]: </span>{otherPdp}</p>
        <p className="whitespace-pre-wrap"><span className="text-gray-500">Other PDP Chapters Checklist: </span>{joined(profileData.otherPdpChaptersList)}</p>
        <p className="whitespace-pre-wrap"><span className="text-gray-500">PDP RM Outcome/Indicator [33]: </span>{value(profileData.pdpOutcomeIndicators)}</p>
        <p className="whitespace-pre-wrap"><span className="text-gray-500">PDP Midterm Update Outcome/Indicator [34][35]: </span>{value(profileData.pdpMuOutcomeIndicators)}</p>
        <p className="whitespace-pre-wrap"><span className="text-gray-500">Main Infrastructure Sector / Subsector [36][37]: </span>{value(profileData.infrastructureSector)}</p>
        <p className="whitespace-pre-wrap"><span className="text-gray-500">Project Readiness [38]: </span>{value(profileData.projectReadiness)}</p>
        <p className="whitespace-pre-wrap"><span className="text-gray-500">Project Readiness Checklist: </span>{joined(profileData.projectReadinessItems)}</p>
        <p className="whitespace-pre-wrap"><span className="text-gray-500">Expected Outputs/Deliverables: </span>{value(profileData.expectedOutputs)}</p>
        <p className="whitespace-pre-wrap"><span className="text-gray-500">8-Point Agenda + SDG: </span>{value(profileData.agendaAndSdg)}</p>
        <div className="grid md:grid-cols-2 gap-x-4 gap-y-1 text-[11px]">
          {[
            "Protect purchasing power",
            "Reduce vulnerability and scarring",
            "Ensure sound macroeconomic fundamentals",
            "Create more jobs",
            "Create quality jobs",
            "Create green jobs",
            "Uphold public order and safety",
            "Ensure level playing field",
          ].map((item) => (
            <div key={item}><Check on={has(profileData.agendaSelections, item)} /> {item}</div>
          ))}
        </div>
        <p className="whitespace-pre-wrap"><span className="text-gray-500">Agenda Checklist: </span>{joined(profileData.agendaSelections)}</p>
        <p className="whitespace-pre-wrap"><span className="text-gray-500">SDG Checklist: </span>{joined(profileData.sdgSelections)}</p>
        <p><span className="text-gray-500">GAD Score: </span>{value(profileData.gadScore)}</p>
        <p><span className="text-gray-500">Level of GAD Responsiveness: </span>{value(profileData.gadResponsiveness)}</p>
        <p><span className="text-gray-500">Employment Generation: </span>{value(profileData.employmentGeneration)}</p>
        <p><span className="text-gray-500">Employment Split (Total/Male/Female): </span>{value(profileData.employmentTotal)} / {value(profileData.employmentMale)} / {value(profileData.employmentFemale)}</p>
        <p className="whitespace-pre-wrap"><span className="text-gray-500">Remarks [39]: </span>{value(profileData.remarks)}</p>
      </section>

      <section className="space-y-1 border border-gray-300 rounded p-3 print:border-black print:rounded-none">
        <h4 className="font-semibold">CONTACT INFORMATION</h4>
        <p className="mt-2 font-medium">FOCAL PERSON</p>
        <p className="whitespace-pre-wrap">{value(profileData.focalPerson)}</p>
        <p className="mt-2 font-medium">ALTERNATIVE REPRESENTATIVE</p>
        <p className="whitespace-pre-wrap">{value(profileData.alternateRepresentative)}</p>
        <p className="mt-2 font-medium">CONTACT DETAILS</p>
        <p className="whitespace-pre-wrap">{value(profileData.contactDetails)}</p>
        <p className="text-[10px] mt-3">
          Kindly return the accomplished Project Profile to the OAGMP-MDPS technical staff on or before 28 November 2025 (Friday) via submission of hard copy to the OAGMP 16th Floor, New MMDA Building, and the soft copy via email: pped@mmda.gov.ph.
        </p>
      </section>
    </div>
  );
};

export default ProjectProfileReadOnly;
