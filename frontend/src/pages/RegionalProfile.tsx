import { useEffect, useMemo, useState } from "react";
import ncrMapImage from "../assets/NCR MAP (2).png";
import cmsApi, { type CMSPageSnapshot } from "../services/cmsApi";

type CityLink = {
  name: string;
  website: string;
  type: "website" | "facebook";
};

type QuickStat = {
  label: string;
  value: string;
  subtext: string;
  icon: string;
  color: string;
};

const FALLBACK_STATS: QuickStat[] = [
  {
    label: "Population",
    value: "13.5M",
    subtext: "2020 Census",
    icon: "people",
    color: "from-blue-500 to-cyan-400",
  },
  {
    label: "GDP Share",
    value: "36%",
    subtext: "National GDP",
    icon: "peso",
    color: "from-green-500 to-emerald-400",
  },
  {
    label: "Land Area",
    value: "619.57 km2",
    subtext: "Metro Manila",
    icon: "map",
    color: "from-purple-500 to-indigo-400",
  },
  {
    label: "Cities & Municipality",
    value: "16 + 1",
    subtext: "Pateros",
    icon: "building",
    color: "from-orange-500 to-red-400",
  },
  {
    label: "Key Sectors",
    value: "Services",
    subtext: "Finance, Trade, BPO",
    icon: "office",
    color: "from-pink-500 to-rose-400",
  },
];

const FALLBACK_OVERVIEW_PARAGRAPHS = [
  "The National Capital Region (NCR), also known as Metropolitan Manila or Metro Manila, is the Philippines' political, economic, educational, and cultural center. It is the smallest region in the country, with a land area of 619.54 square kilometers, and the most densely populated, home to more than 13 million Filipinos.",
  "Located in central Luzon, NCR sits on the eastern coast of Manila Bay at the mouth of the Pasig River. It is bordered by Manila Bay to the west, Central Luzon to the north, Laguna de Bay to the south, and the Sierra Madre mountains to the east.",
  "NCR is the only region in the Philippines without provinces. It is composed of 17 local government units: 16 cities (Caloocan, Malabon, Navotas, Valenzuela, Quezon City, Marikina, Pasig, Taguig, Makati, Manila, Mandaluyong, San Juan, Pasay, Paranaque, Las Pinas, and Muntinlupa) and one municipality, Pateros.",
];

const FALLBACK_CITIES: CityLink[] = [
  { name: "Manila", website: "https://www.manila.gov.ph", type: "website" },
  { name: "Quezon City", website: "https://www.quezoncity.gov.ph", type: "website" },
  { name: "Caloocan", website: "https://caloocancity.gov.ph", type: "facebook" },
  { name: "Las Pinas", website: "https://laspinascity.gov.ph/", type: "facebook" },
  { name: "Makati", website: "https://www.makati.gov.ph", type: "website" },
  { name: "Malabon", website: "https://malabon.gov.ph", type: "facebook" },
  { name: "Mandaluyong", website: "https://mandaluyong.gov.ph", type: "facebook" },
  { name: "Marikina", website: "https://marikina.gov.ph", type: "facebook" },
  { name: "Muntinlupa", website: "https://muntinlupacity.gov.ph", type: "facebook" },
  { name: "Navotas", website: "https://navotas.gov.ph", type: "facebook" },
  { name: "Paranaque", website: "https://paranaque.gov.ph", type: "facebook" },
  { name: "Pasay", website: "https://pasay.gov.ph", type: "facebook" },
  { name: "Pasig", website: "https://pasigcity.gov.ph", type: "website" },
  { name: "San Juan", website: "https://sanjuancity.gov.ph", type: "facebook" },
  { name: "Taguig", website: "https://taguig.gov.ph", type: "website" },
  { name: "Valenzuela", website: "https://valenzuela.gov.ph", type: "facebook" },
  { name: "Pateros", website: "https://www.pateros.gov.ph", type: "facebook" },
];

const asRecord = (value: unknown): Record<string, unknown> =>
  value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};

const asArray = (value: unknown): unknown[] => (Array.isArray(value) ? value : []);

const asString = (value: unknown, fallback = "") =>
  typeof value === "string" && value.trim() ? value.trim() : fallback;

const getRegionSection = (page: CMSPageSnapshot | null, sectionKey: string) =>
  page?.sections.find((section) => section.sectionKey === sectionKey)?.content ?? null;

const statIcon = (key: string) => {
  const normalized = key.toLowerCase();
  if (normalized.includes("peso") || normalized.includes("money") || normalized.includes("gdp")) {
    return (
      <path d="M7 5h7a4 4 0 010 8H7m0-8v14m0-8h8m-8 4h6" />
    );
  }
  if (normalized.includes("map") || normalized.includes("area")) {
    return (
      <path d="M9 18l-6 3V6l6-3 6 3 6-3v15l-6 3-6-3zm0 0V3m6 18V6" />
    );
  }
  if (normalized.includes("building") || normalized.includes("office") || normalized.includes("sector")) {
    return (
      <path d="M4 21V5a2 2 0 012-2h8a2 2 0 012 2v16M9 7h2m-2 4h2m-2 4h2m7-6h2a2 2 0 012 2v10" />
    );
  }
  return (
    <path d="M16 11a4 4 0 10-8 0 4 4 0 008 0zm-9 8a7 7 0 0110 0M19 8v6m3-3h-6" />
  );
};

const statsFromContent = (content: Record<string, unknown>): QuickStat[] => {
  const items = asArray(content.stats)
    .map((item) => {
      const row = asRecord(item);
      const label = asString(row.label);
      const value = asString(row.value);
      if (!label || !value) return null;
      return {
        label,
        value,
        subtext: asString(row.subtext),
        icon: asString(row.icon, "people"),
        color: asString(row.color, "from-blue-500 to-cyan-400"),
      };
    })
    .filter(Boolean) as QuickStat[];
  return items.length ? items : FALLBACK_STATS;
};

const citiesFromContent = (content: Record<string, unknown>): CityLink[] => {
  const items = asArray(content.items)
    .map((item) => {
      const row = asRecord(item);
      const name = asString(row.name || row.title);
      const website = asString(row.website || row.link);
      const type = asString(row.type, "website") === "facebook" ? "facebook" : "website";
      return name && website ? { name, website, type } : null;
    })
    .filter(Boolean) as CityLink[];
  return items.length ? items : FALLBACK_CITIES;
};

export default function RegionalProfile() {
  const [cmsPage, setCmsPage] = useState<CMSPageSnapshot | null>(null);

  useEffect(() => {
    let mounted = true;
    cmsApi
      .getPublicPage("regional-profile")
      .then((page) => {
        if (mounted) setCmsPage(page);
      })
      .catch(() => {
        if (mounted) setCmsPage(null);
      });
    return () => {
      mounted = false;
    };
  }, []);

  const hero = asRecord(getRegionSection(cmsPage, "region-hero"));
  const overview = asRecord(getRegionSection(cmsPage, "regional-overview"));
  const coverage = asRecord(getRegionSection(cmsPage, "geographic-coverage"));
  const lguDirectory = asRecord(getRegionSection(cmsPage, "lgu-directory"));

  const overviewParagraphs = useMemo(() => {
    const paragraphs = asArray(overview.paragraphs)
      .map((item) => asString(item))
      .filter(Boolean);
    return paragraphs.length ? paragraphs : FALLBACK_OVERVIEW_PARAGRAPHS;
  }, [overview.paragraphs]);

  const quickStats = useMemo(() => statsFromContent(overview), [overview]);
  const cities = useMemo(() => citiesFromContent(lguDirectory), [lguDirectory]);

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white">
      <header className="bg-gradient-to-r from-[#012a5a] via-[#0b6fb7] to-[#0d8fb3] text-white">
        <div className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-4xl text-center">
            <div className="mb-4 inline-block">
              <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-2xl border border-white/20 bg-white/10 backdrop-blur-sm">
                <svg className="h-12 w-12 text-white" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                  <path d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
            </div>
            <h1 className="mb-4 text-4xl font-extrabold md:text-5xl">
              {asString(hero.title, "NCR Region Profile")}
            </h1>
            <p className="text-lg text-white/90">
              {asString(
                hero.subtitle,
                "Geography, demographics, economy, and development context of the National Capital Region",
              )}
            </p>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl space-y-16 px-4 py-12 sm:px-6 lg:px-8">
        <section className="rounded-3xl bg-white p-8 shadow-sm lg:p-12">
          <div className="grid grid-cols-1 items-center gap-12 lg:grid-cols-2">
            <div>
              <h2 className="mb-4 text-3xl font-bold text-slate-900">
                {asString(overview.title, "Regional Overview")}
              </h2>
              <div className="space-y-5">
                {overviewParagraphs.map((paragraph, index) => (
                  <p key={index} className="text-slate-700">
                    {paragraph}
                  </p>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-6 md:grid-cols-3">
              {quickStats.slice(0, 6).map((stat) => (
                <div key={stat.label} className="flex flex-col items-center p-4">
                  <div className={`mb-3 flex h-16 w-16 items-center justify-center rounded-xl bg-gradient-to-br ${stat.color}`}>
                    <svg className="h-8 w-8 text-white" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                      {statIcon(stat.icon || stat.label)}
                    </svg>
                  </div>
                  <div className="text-center">
                    <div className="mb-1 text-2xl font-extrabold text-slate-900">{stat.value}</div>
                    <div className="mb-1 text-sm font-semibold text-slate-600">{stat.label}</div>
                    <div className="text-xs text-slate-500">{stat.subtext}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section>
          <div className="mb-10 text-center">
            <h2 className="mb-3 text-3xl font-bold text-slate-900">
              {asString(coverage.title, "Geographic Coverage")}
            </h2>
            <p className="mx-auto max-w-2xl text-slate-600">
              {asString(coverage.subtitle, "Metro Manila comprises 16 cities and 1 municipality")}
            </p>
          </div>

          <div className="grid grid-cols-1 gap-8 lg:grid-cols-3">
            <div className="lg:col-span-2">
              <div className="rounded-2xl border border-slate-100 bg-white p-6 shadow-lg">
                <div className="overflow-hidden rounded-xl border-2 border-slate-200 bg-slate-50">
                  <img src={ncrMapImage} alt="Metro Manila Map" className="h-auto w-full object-cover" />
                </div>
                <div className="mt-4 text-center text-sm text-slate-600">
                  {asString(coverage.caption, "Political map showing the 16 cities and 1 municipality of NCR")}
                </div>
              </div>
            </div>

            <div className="lg:col-span-1">
              <div className="rounded-2xl border border-slate-100 bg-white p-6 shadow-lg">
                <h3 className="mb-4 flex items-center gap-2 text-xl font-bold text-slate-900">
                  <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-100">
                    <svg className="h-5 w-5 text-blue-700" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                      <path d="M3 21h18M5 21V7l8-4v18M19 21V11l-6-4M9 9h1m-1 4h1m-1 4h1m6-4h1m-1 4h1" />
                    </svg>
                  </span>
                  {asString(lguDirectory.title, "Local Government Units")}
                </h3>
                <div className="max-h-[450px] space-y-2 overflow-y-auto">
                  {cities.map((city, index) => (
                    <a
                      key={`${city.name}-${index}`}
                      href={city.website}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="group flex cursor-pointer items-center gap-3 rounded-lg border border-transparent bg-slate-50 p-3 transition hover:border-blue-300 hover:bg-blue-50"
                      title={`Visit ${city.name} official ${city.type === "website" ? "website" : "Facebook page"}`}
                    >
                      <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-blue-600 text-sm font-bold text-white">
                        {index + 1}
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="font-semibold text-slate-900 transition group-hover:text-blue-600">{city.name}</div>
                        {city.name.toLowerCase() === "pateros" && <div className="text-xs text-slate-500">Municipality</div>}
                      </div>
                      <svg className="h-4 w-4 flex-shrink-0 text-slate-400 transition group-hover:text-blue-600" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                        <path d="M9 5l7 7-7 7" />
                      </svg>
                    </a>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
