import React from "react";

const PrintAppendix: React.FC = () => {
  return (
    <div className="print-token text-[11px] space-y-4">
      <div className="print-page-break border border-black p-3">
        <h4 className="font-bold mb-2">ANNEX: FIELD GUIDANCE [14]-[18]</h4>
        <p>[14] Spatial Coverage - By Impact: Choose Nationwide, Interregional, Region-Specific, or Abroad based on impact coverage.</p>
        <p>[15] River Basins: Select if flood management PAP covers river basin/s.</p>
        <p>[16] Major River Basin: Drainage area greater than 1,000 sq km.</p>
        <p>[17] Principal River Basin: Drainage area greater than 40 sq km.</p>
        <p>[18] PIP Typology: Classify PAPs as capital investment, technical assistance, relending, or government facilities.</p>
      </div>

      <div className="print-page-break border border-black p-3">
        <h4 className="font-bold mb-2">ANNEX: PROGRAMMING REFERENCES [19]-[23]</h4>
        <p>[19] Core Investment Programs and Projects (CIP): Big-ticket PAPs requiring ICC/ED Council process.</p>
        <p>[20] TRIP: National government-funded infrastructure PAPs for the rolling three-year window.</p>
        <p>[21] ARNIPAP: Regional priority PAPs agreed during RNIP dialogue.</p>
        <p>[22] CIPs readiness category and approval process reference.</p>
        <p>[23] Non-CIPs category reference.</p>
      </div>

      <div className="print-page-break border border-black p-3">
        <h4 className="font-bold mb-2">ANNEX: IMPLEMENTATION NOTES [24]-[31]</h4>
        <p>[24] Implementation Risk: Identify material risks that may delay/stop execution.</p>
        <p>[25] Mitigation Strategies: Corresponding action plan for each listed risk.</p>
        <p>[26] PAP Code: 15-digit UACS code for the PAP.</p>
        <p>[27] Updates: Provide latest implementation/financial progress details.</p>
        <p>[28] Update as of: Include reference date (month/day/year).</p>
        <p>[29][30] Project Cost: Provide exact PHP values by funding source and year.</p>
        <p>[31] PIP-Budget Tracker: Record OSBPS, NEP, and GAA figures per year.</p>
      </div>

      <div className="print-page-break border border-black p-3">
        <h4 className="font-bold mb-2">ANNEX: PDP / RM / READINESS NOTES [32]-[39]</h4>
        <p>[32] Other PDP Chapters: Select all additional relevant chapters.</p>
        <p>[33] PDP Results Matrix Outcome/Indicator mapping.</p>
        <p>[34] PDP Midterm Update chapter reference.</p>
        <p>[35] PDP Midterm Update RM mapping.</p>
        <p>[36][37] Main and other infrastructure sector/subsector classification.</p>
        <p>[38] Project readiness checklist and documentary compliance.</p>
        <p>[39] Remarks: Other pertinent implementation notes.</p>
      </div>
    </div>
  );
};

export default PrintAppendix;
