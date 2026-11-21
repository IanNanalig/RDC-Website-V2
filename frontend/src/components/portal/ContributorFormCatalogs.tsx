import React, { useEffect, useState } from "react";
import { api } from "../../services/api";

type Location = { code: string; name: string; map_key: string; kind: string; region: string; is_active: boolean };
type Committee = { code: string; acronym: string; name: string; description: string; is_active: boolean; groups: string[] };
type Catalogs = { locations: Location[]; committees: Committee[]; groups: { value: string; label: string }[] };

const endpoint = "admin/contributor-form-catalogs/";
const emptyCommittee: Committee = { code: "", acronym: "", name: "", description: "", is_active: false, groups: [] };
const inputClass = "block w-full rounded-md border border-slate-300 px-2 py-1.5";

export default function ContributorFormCatalogs({ onUpdated }: { onUpdated: () => void }) {
  const [data, setData] = useState<Catalogs | null>(null);
  const [location, setLocation] = useState<Location | null>(null);
  const [committee, setCommittee] = useState<Committee | null>(null);
  const [creating, setCreating] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [failure, setFailure] = useState("");

  useEffect(() => {
    let active = true;
    api.get(endpoint, true).then((catalogs: Catalogs) => {
      if (active) setData(catalogs);
    }).catch((error: Error) => {
      if (active) setFailure(error.message);
    });
    return () => { active = false; };
  }, []);

  async function save(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setFailure("");
    setNotice("");
    try {
      if (location) {
        await api.patch(`${endpoint}locations/${location.code}/`, { name: location.name, is_active: location.is_active });
      } else if (committee && creating) {
        await api.post(`${endpoint}committees/`, committee);
      } else if (committee) {
        await api.patch(`${endpoint}committees/${committee.code}/`, committee);
      }
      const next = await api.get(endpoint, true);
      setData(next);
      setLocation(null);
      setCommittee(null);
      setNotice("Catalog updated.");
      onUpdated();
    } catch (error) {
      setFailure(error instanceof Error ? error.message : "Catalog update failed.");
    } finally {
      setBusy(false);
    }
  }

  const editLocation = (entry: Location) => { setCommittee(null); setLocation(entry); };
  const editCommittee = (entry: Committee, isNew = false) => {
    setLocation(null);
    setCreating(isNew);
    setCommittee(entry);
  };

  return (
    <section className="portal-card p-4">
      {failure && <p role="alert" className="mb-3 text-sm text-rose-700">{failure}</p>}
      {notice && <p role="status" className="mb-3 text-sm text-emerald-700">{notice}</p>}
      {!data && !failure && <p role="status">Loading catalogs…</p>}
      {data && <div className="grid gap-4 md:grid-cols-2">
        <div>
          <h3 className="font-semibold text-slate-900">Location Catalog</h3>
          <ul className="mt-2 space-y-1">
            {data.locations.map((entry) => <li key={entry.code}>
              <button type="button" className="text-left text-sm text-blue-700" onClick={() => editLocation(entry)}>
                {entry.name}{entry.is_active ? "" : " (inactive)"}
              </button>
            </li>)}
          </ul>
        </div>
        <div>
          <h3 className="font-semibold text-slate-900">RDC-NCR Sectoral Committee Catalog</h3>
          <ul className="mt-2 space-y-2">
            {data.committees.map((entry) => <li key={entry.code}>
              <button type="button" className="text-left text-sm text-blue-700" onClick={() => editCommittee(entry)}>
                {entry.acronym} · {entry.name}{entry.is_active ? "" : " (inactive)"}
              </button>
              <p className="text-xs text-slate-600">
                {entry.groups.map((group) => data.groups.find((item) => item.value === group)?.label || group).join(", ") || "No linked outcome groups"}
              </p>
            </li>)}
          </ul>
          <button type="button" className="portal-btn portal-btn-ghost mt-3" onClick={() => editCommittee(emptyCommittee, true)}>Add committee</button>
        </div>
      </div>}
      {(location || committee) && <form onSubmit={save} className="mt-4 max-w-xl rounded-lg border border-slate-200 p-3">
        <fieldset disabled={busy} className="space-y-2">
          <legend className="font-semibold text-slate-900">{location ? `Edit ${location.map_key}` : creating ? "Add committee" : `Edit ${committee?.acronym}`}</legend>
          {location && <>
            <p className="text-xs text-slate-600">{location.region} · {location.kind} · Map key {location.map_key}</p>
            <label className="block text-sm">Name<input className={inputClass} required maxLength={100} value={location.name} onChange={(event) => setLocation({ ...location, name: event.target.value })} /></label>
            <label className="flex gap-2 text-sm"><input type="checkbox" checked={location.is_active} onChange={(event) => setLocation({ ...location, is_active: event.target.checked })} />Available to Contributors</label>
          </>}
          {committee && <>
            <label className="block text-sm">Code<input className={inputClass} required maxLength={40} pattern="[a-z0-9_-]+" readOnly={!creating} value={committee.code} onChange={(event) => setCommittee({ ...committee, code: event.target.value })} /></label>
            <label className="block text-sm">Acronym<input className={inputClass} required maxLength={30} value={committee.acronym} onChange={(event) => setCommittee({ ...committee, acronym: event.target.value })} /></label>
            <label className="block text-sm">Name<input className={inputClass} required maxLength={180} value={committee.name} onChange={(event) => setCommittee({ ...committee, name: event.target.value })} /></label>
            <label className="block text-sm">Description<textarea className={inputClass} value={committee.description} onChange={(event) => setCommittee({ ...committee, description: event.target.value })} /></label>
            <fieldset className="space-y-1">
              <legend className="text-sm font-medium">Linked outcome groups</legend>
              {data?.groups.map((group) => <label key={group.value} className="flex gap-2 text-sm">
                <input type="checkbox" checked={committee.groups.includes(group.value)} onChange={(event) => setCommittee({
                  ...committee,
                  groups: event.target.checked ? [...committee.groups, group.value] : committee.groups.filter((value) => value !== group.value),
                })} />{group.label}
              </label>)}
            </fieldset>
            <label className="flex gap-2 text-sm"><input type="checkbox" checked={committee.is_active} onChange={(event) => setCommittee({ ...committee, is_active: event.target.checked })} />Available to Contributors</label>
          </>}
          <div className="flex gap-2">
            <button className="portal-btn portal-btn-primary" type="submit">{busy ? "Saving…" : "Save catalog entry"}</button>
            <button className="portal-btn portal-btn-ghost" type="button" onClick={() => { setCommittee(null); setLocation(null); }}>Cancel</button>
          </div>
        </fieldset>
      </form>}
    </section>
  );
}
