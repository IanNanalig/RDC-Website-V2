import ncrMapImage from "../assets/NCR MAP (2).png";

type CityLink = {
  name: string;
  website: string;
  type: "website" | "facebook";
};

const QUICK_STATS = [
  {
    label: "Population",
    value: "13.5M",
    subtext: "2020 Census",
    icon: "👥",
    color: "from-blue-500 to-cyan-400",
  },
  {
    label: "GDP Share",
    value: "36%",
    subtext: "National GDP",
    icon: "💰",
    color: "from-green-500 to-emerald-400",
  },
  {
    label: "Land Area",
    value: "619.57 km²",
    subtext: "Metro Manila",
    icon: "🗺️",
    color: "from-purple-500 to-indigo-400",
  },
  {
    label: "Cities & Municipality",
    value: "16 + 1",
    subtext: "Pateros",
    icon: "🏛️",
    color: "from-orange-500 to-red-400",
  },
  {
    label: "Key Sectors",
    value: "Services",
    subtext: "Finance, Trade, BPO",
    icon: "🏢",
    color: "from-pink-500 to-rose-400",
  },
];

const CITIES_WITH_LINKS: CityLink[] = [
  { name: "Manila", website: "https://www.manila.gov.ph", type: "website" },
  {
    name: "Quezon City",
    website: "https://www.quezoncity.gov.ph",
    type: "website",
  },
  {
    name: "Caloocan",
    website: "https://caloocancity.gov.ph",
    type: "facebook",
  },
  {
    name: "Las Piñas",
    website: "https://laspinascity.gov.ph/",
    type: "facebook",
  },
  { name: "Makati", website: "https://www.makati.gov.ph", type: "website" },
  {
    name: "Malabon",
    website: "https://malabon.gov.ph",
    type: "facebook",
  },
  {
    name: "Mandaluyong",
    website: "https://mandaluyong.gov.ph",
    type: "facebook",
  },
  {
    name: "Marikina",
    website: "https://marikina.gov.ph",
    type: "facebook",
  },
  {
    name: "Muntinlupa",
    website: "https://muntinlupacity.gov.ph",
    type: "facebook",
  },
  {
    name: "Navotas",
    website: "https://navotas.gov.ph",
    type: "facebook",
  },
  {
    name: "Parañaque",
    website: "https://paranaque.gov.ph",
    type: "facebook",
  },
  {
    name: "Pasay",
    website: "https://pasay.gov.ph",
    type: "facebook",
  },
  { name: "Pasig", website: "https://pasigcity.gov.ph", type: "website" },
  {
    name: "San Juan",
    website: "https://sanjuancity.gov.ph",
    type: "facebook",
  },
  { name: "Taguig", website: "https://taguig.gov.ph", type: "website" },
  {
    name: "Valenzuela",
    website: "https://valenzuela.gov.ph",
    type: "facebook",
  },
  {
    name: "Pateros",
    website: "https://www.pateros.gov.ph",
    type: "facebook",
  },
];

export default function RegionProfile() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white">
      {/* Header */}
      <header className="bg-gradient-to-r from-[#012a5a] via-[#0b6fb7] to-[#0d8fb3] text-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
          <div className="max-w-4xl mx-auto text-center">
            <div className="inline-block mb-4">
              <div className="w-20 h-20 bg-white/10 backdrop-blur-sm rounded-2xl flex items-center justify-center border border-white/20 mx-auto">
                <svg
                  className="w-12 h-12 text-white"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  viewBox="0 0 24 24"
                >
                  <path d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
            </div>
            <h1 className="text-4xl md:text-5xl font-extrabold mb-4">
              NCR Region Profile
            </h1>
            <p className="text-lg text-white/90">
              Geography, demographics, economy, and development context of the
              National Capital Region
            </p>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 space-y-16">
        {/* Regional Overview Section - Updated with icons on right */}
        <section className="bg-white rounded-3xl p-8 lg:p-12 shadow-sm">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
            {/* Text on the left */}
            <div>
              <h2 className="text-3xl font-bold text-slate-900 mb-4">
                Regional Overview
              </h2>
              <p className="text-slate-700 mb-6">
                The National Capital Region (NCR), also known as Metropolitan
                Manila or Metro Manila, is the Philippines’ political, economic,
                educational, and cultural center. It is the smallest region in
                the country, with a land area of 619.54 square kilometers, and
                the most densely populated, home to more than 13 million
                Filipinos.
              </p>
              <p className="text-slate-700">
                Located in central Luzon, NCR sits on the eastern coast of
                Manila Bay at the mouth of the Pasig River. It is bordered by
                Manila Bay to the west, Central Luzon to the north, Laguna de
                Bay to the south, and the Sierra Madre mountains to the east.
              </p>
              <br />
              <p className="text-slate-700">
                NCR is the only region in the Philippines without provinces. It
                is composed of 17 local government units: 16 cities (Caloocan,
                Malabon, Navotas, Valenzuela, Quezon City, Marikina, Pasig,
                Taguig, Makati, Manila, Mandaluyong, San Juan, Pasay, Parañaque,
                Las Piñas, and Muntinlupa) and one municipality, Pateros.
              </p>
            </div>

            {/* Icons on the right - Like the About RDC layout */}
            <div className="grid grid-cols-2 md:grid-cols-3 gap-6">
              {QUICK_STATS.slice(0, 5).map((stat) => (
                <div
                  key={stat.label}
                  className="flex flex-col items-center p-4"
                >
                  <div
                    className={`w-16 h-16 rounded-xl bg-gradient-to-br ${stat.color} flex items-center justify-center text-3xl mb-3`}
                  >
                    {stat.icon}
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-extrabold text-slate-900 mb-1">
                      {stat.value}
                    </div>
                    <div className="text-sm font-semibold text-slate-600 mb-1">
                      {stat.label}
                    </div>
                    <div className="text-xs text-slate-500">{stat.subtext}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Regional Map Section */}
        <section>
          <div className="text-center mb-10">
            <h2 className="text-3xl font-bold text-slate-900 mb-3">
              Geographic Coverage
            </h2>
            <p className="text-slate-600 max-w-2xl mx-auto">
              Metro Manila comprises 16 cities and 1 municipality
            </p>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Map */}
            <div className="lg:col-span-2">
              <div className="bg-white rounded-2xl shadow-lg p-6 border border-slate-100">
                <div className="bg-slate-50 rounded-xl overflow-hidden border-2 border-slate-200">
                  <img
                    src={ncrMapImage}
                    alt="Metro Manila Map"
                    className="w-full h-auto object-cover"
                  />
                </div>
                <div className="mt-4 text-sm text-slate-600 text-center">
                  Political map showing the 16 cities and 1 municipality of NCR
                </div>
              </div>
            </div>

            {/* Cities List */}
            <div className="lg:col-span-1">
              <div className="bg-white rounded-2xl shadow-lg p-6 border border-slate-100">
                <h3 className="text-xl font-bold text-slate-900 mb-4 flex items-center gap-2">
                  <span className="w-8 h-8 bg-blue-100 rounded-lg flex items-center justify-center">
                    🏙️
                  </span>
                  Local Government Units
                </h3>
                <div className="space-y-2 max-h-[450px] overflow-y-auto">
                  {CITIES_WITH_LINKS.map((city, index) => (
                    <a
                      key={city.name}
                      href={city.website}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-3 p-3 rounded-lg bg-slate-50 hover:bg-blue-50 hover:border-blue-300 transition border border-transparent cursor-pointer group"
                      title={`Visit ${city.name} official ${
                        city.type === "website" ? "website" : "Facebook page"
                      }`}
                    >
                      <div className="w-8 h-8 bg-blue-600 text-white rounded-lg flex items-center justify-center font-bold text-sm flex-shrink-0">
                        {index + 1}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="font-semibold text-slate-900 group-hover:text-blue-600 transition">
                          {city.name}
                        </div>
                        {city.name === "Pateros" && (
                          <div className="text-xs text-slate-500">
                            Municipality
                          </div>
                        )}
                      </div>
                      <svg
                        className="w-4 h-4 text-slate-400 group-hover:text-blue-600 transition flex-shrink-0"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        viewBox="0 0 24 24"
                      >
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
