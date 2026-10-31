import React, { useEffect, useMemo, useState } from "react";
import { ABOUT_ORGANIZATION_NODE_IDS } from "../content/aboutStructure";
import cmsApi, { type CMSPageSnapshot } from "../services/cmsApi";
import { canDownloadDocument, downloadDocument } from "../utils/documentDownload";

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

const asRecord = (value: unknown): Record<string, unknown> =>
  value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};

const asArray = (value: unknown): unknown[] => (Array.isArray(value) ? value : []);

const asString = (value: unknown, fallback = "") =>
  typeof value === "string" && value.trim() ? value.trim() : fallback;

const asNumber = (value: unknown, fallback?: number) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
};

const isVisible = (value: unknown) => {
  const row = asRecord(value);
  return row.isVisible !== false && row.visible !== false;
};

const dotColorClass = (color: string) => ({
  blue: "bg-blue-600",
  amber: "bg-amber-600",
  purple: "bg-purple-600",
  emerald: "bg-emerald-600",
  green: "bg-green-600",
  slate: "bg-slate-600",
}[color] || "bg-slate-600");

const textColorClass = (color: string) => ({
  blue: "text-blue-600",
  amber: "text-amber-600",
  purple: "text-purple-600",
  emerald: "text-emerald-600",
  green: "text-green-600",
  slate: "text-slate-700",
}[color] || "text-slate-700");

const getAboutSection = (page: CMSPageSnapshot | null, sectionKey: string) =>
  page?.sections.find((section) => section.sectionKey === sectionKey)?.content ?? null;

const aboutIcon = (value: unknown, fallback: string) => {
  const icons: Record<string, string> = {
    book: "\u{1F4D6}",
    building: "\u{1F3DB}\uFE0F",
    clipboard: "\u{1F4CB}",
    crown: "\u{1F451}",
    document: "\u{1F4DC}",
    file: "\u{1F4C4}",
    handshake: "\u{1F91D}",
    lightbulb: "\u{1F4A1}",
    scale: "\u2696\uFE0F",
    search: "\u{1F50D}",
  };
  const key = asString(value).toLowerCase();
  const fallbackKey = asString(fallback).toLowerCase();
  return icons[key] || icons[fallbackKey] || icons.document;
};

// Committee Data
type Committee = {
  id: string;
  title: string;
  description: string;
  icon: string;
  color: string;
  url?: string;
  content: {
    overview: string;
    functions: string[];
    members: string[];
  };
};

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

const CommitteeModal: React.FC<{
  committee: Committee | null;
  detailedCommittee: DetailedCommittee | null;
  onClose: () => void;
}> = ({ committee, detailedCommittee, onClose }) => {
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  if (!committee) return null;

  const hasDetailedInfo = detailedCommittee && detailedCommittee.subSections;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black bg-opacity-50" onClick={onClose} />

      {/* Modal Container */}
      <div className="flex min-h-full items-center justify-center p-4">
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="committee-dialog-title"
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
                  <h2 id="committee-dialog-title" className="text-3xl font-bold">{committee.title}</h2>
                  <p className="text-white/90 mt-2">{committee.description}</p>
                </div>
              </div>
              <button
                type="button"
                aria-label="Close committee details"
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

            {committee.content.functions.length > 0 && (
              <div className="mb-8">
                <h3 className="text-xl font-bold text-slate-900 mb-4">Functions</h3>
                <ul className="space-y-3">
                  {committee.content.functions.map((item, index) => (
                    <li key={index} className="flex items-start gap-3">
                      <span className="mt-2 h-2 w-2 flex-shrink-0 rounded-full bg-blue-600" />
                      <span className="text-slate-700">{item}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

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
            <div className="mt-8 pt-6 border-t border-slate-200 flex flex-wrap justify-end gap-3">
              {committee.url && (
                <a
                  href={committee.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-6 py-3 bg-slate-100 text-slate-800 rounded-lg font-medium hover:bg-slate-200 transition"
                >
                  Open Committee Document
                </a>
              )}
              <button
                type="button"
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
  const [aboutCmsPage, setAboutCmsPage] = useState<CMSPageSnapshot | null>(null);
  const [aboutLoadState, setAboutLoadState] = useState<"loading" | "ready" | "error">("loading");
  const [selectedNode, setSelectedNode] = useState<string | null>(
    "chairperson",
  );
  const [selectedCommittee, setSelectedCommittee] = useState<Committee | null>(
    null,
  );
  const [selectedDetailedCommittee, setSelectedDetailedCommittee] =
    useState<DetailedCommittee | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [expandedYears, setExpandedYears] = useState<string[]>([]);
  const [downloadingDocumentId, setDownloadingDocumentId] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    cmsApi
      .getPublicPage("about-rdc")
      .then((page) => {
        if (active) {
          setAboutCmsPage(page);
          setAboutLoadState("ready");
        }
      })
      .catch(() => {
        if (active) {
          setAboutCmsPage(null);
          setAboutLoadState("error");
        }
      });
    return () => {
      active = false;
    };
  }, []);

  const heroContent = getAboutSection(aboutCmsPage, "about-hero");
  const legalContent = getAboutSection(aboutCmsPage, "legal-basis");
  const committeesContent = getAboutSection(aboutCmsPage, "committees");
  const organizationContent = getAboutSection(aboutCmsPage, "organization-structure");
  const resolutionsContent = getAboutSection(aboutCmsPage, "resolutions-archive");

  const legalDocuments = useMemo(() => {
    const cmsRows = asArray(asRecord(legalContent).documents || asRecord(legalContent).items);
    const documents: LegalDocument[] = [];

    cmsRows.map(asRecord).forEach((row, index) => {
      const rowId = asString(row.id);
      const matchedIndex = documents.findIndex(
        (doc) => doc.id === rowId || doc.title === asString(row.title),
      );
      if (!isVisible(row)) {
        if (matchedIndex >= 0) documents.splice(matchedIndex, 1);
        return;
      }

      const fallback = matchedIndex >= 0 ? documents[matchedIndex] : undefined;
      const document: LegalDocument = {
        id: rowId || `legal-document-${index + 1}`,
        title: asString(row.title, `Legal Document ${index + 1}`),
        description: asString(row.description),
        icon: aboutIcon(row.icon, "document"),
        color: asString(row.color, "from-blue-600 to-cyan-500"),
        url: asString(row.url || row.link),
        fileType: asString(row.fileType, "Document"),
        fileSize: asString(row.fileSize),
        pages: asNumber(row.pages, fallback?.pages),
      };
      if (matchedIndex >= 0) documents[matchedIndex] = document;
      else documents.push(document);
    });

    return documents;
  }, [legalContent]);

  const committees = useMemo(() => {
    const cmsRows = asArray(asRecord(committeesContent).items);
    const entries: Committee[] = [];

    cmsRows.map(asRecord).forEach((row, index) => {
      const rowId = asString(row.id);
      const matchedIndex = entries.findIndex(
        (committee) => committee.id === rowId || committee.title === asString(row.title),
      );
      if (!isVisible(row)) {
        if (matchedIndex >= 0) entries.splice(matchedIndex, 1);
        return;
      }

      const nestedContent = asRecord(row.content);
      const hasFunctions = Array.isArray(row.functions) || Array.isArray(nestedContent.functions);
      const hasMembers = Array.isArray(row.members) || Array.isArray(nestedContent.members);
      const functions = asArray(row.functions || nestedContent.functions)
        .map((item) => asString(item))
        .filter(Boolean);
      const members = asArray(row.members || nestedContent.members)
        .map((item) => asString(item))
        .filter(Boolean);
      const entry: Committee = {
        id: rowId || `committee-${index + 1}`,
        title: asString(row.title, `Committee ${index + 1}`),
        description: asString(row.description),
        icon: aboutIcon(row.icon, "building"),
        color: asString(row.color, "from-blue-500 to-blue-600"),
        url: asString(row.url || row.link) || undefined,
        content: {
          overview: asString(row.overview || nestedContent.overview),
          functions: hasFunctions ? functions : [],
          members: hasMembers ? members : [],
        },
      };
      if (matchedIndex >= 0) entries[matchedIndex] = entry;
      else entries.push(entry);
    });

    return entries;
  }, [committeesContent]);

  const organizationNodes = useMemo(() => {
    const cmsNodes = asArray(asRecord(organizationContent).nodes).map(asRecord);
    return ABOUT_ORGANIZATION_NODE_IDS.map((id) => {
      const row = cmsNodes.find((node) => asString(node.id) === id) || {};
      const items = asArray(row.items).map((item) => asString(item)).filter(Boolean);
      return {
        id,
        label: asString(row.label),
        title: asString(row.title),
        subtitle: asString(row.subtitle),
        items,
      };
    });
  }, [organizationContent]);

  const organizationNode = (id: string) =>
    organizationNodes.find((node) => node.id === id) || {
      id,
      label: "",
      title: "",
      subtitle: "",
      items: [] as string[],
    };

  const resolutionYears = useMemo(() => {
    const years: Array<{
      year: string;
      content: Array<{ title: string; number: string; description: string; date: string; url: string }>;
    }> = [];

    asArray(asRecord(resolutionsContent).years).map(asRecord).forEach((row) => {
      const year = typeof row.year === "number" || typeof row.year === "string"
        ? String(row.year).trim()
        : "";
      if (!/^\d{4}$/.test(year)) return;
      const content = asArray(row.resolutions || row.items || row.content)
        .map((item) => {
          if (typeof item === "string") return { title: asString(item), number: "", description: "", date: "", url: "" };
          const record = asRecord(item);
          if (!isVisible(record)) return null;
          return {
            title: asString(record.title || record.name),
            number: asString(record.number || record.resolutionNumber),
            description: asString(record.description),
            date: asString(record.date),
            url: asString(record.url || record.link),
          };
        })
        .filter((item): item is { title: string; number: string; description: string; date: string; url: string } => Boolean(item?.title));
      const matchedIndex = years.findIndex((entry) => entry.year === year);
      if (matchedIndex >= 0 && row.replaceExisting !== true) {
        const mergedContent = [...years[matchedIndex].content];
        content.forEach((resolution) => {
          const resolutionIndex = mergedContent.findIndex((item) => item.title === resolution.title);
          if (resolutionIndex >= 0) mergedContent[resolutionIndex] = resolution;
          else mergedContent.push(resolution);
        });
        years[matchedIndex] = { year, content: mergedContent };
      } else if (matchedIndex >= 0) {
        years[matchedIndex] = { year, content };
      } else {
        years.push({ year, content });
      }
    });

    return years;
  }, [resolutionsContent]);

  const resolutionDateRange = useMemo(() => {
    const values = resolutionYears
      .map((entry) => Number(entry.year.match(/\d{4}/)?.[0]))
      .filter((value) => Number.isFinite(value))
      .sort((left, right) => left - right);
    if (!values.length) return "Archive";
    return values[0] === values[values.length - 1]
      ? String(values[0])
      : `${values[0]}-${values[values.length - 1]}`;
  }, [resolutionYears]);

  const resolutionLegendItems = useMemo(() =>
    asArray(asRecord(resolutionsContent).legendItems)
      .map(asRecord)
      .map((row) => ({ label: asString(row.label), color: asString(row.color, "slate") }))
      .filter((row) => row.label),
  [resolutionsContent]);

  const resolutionCategoryItems = useMemo(() =>
    asArray(asRecord(resolutionsContent).categoryItems)
      .map(asRecord)
      .map((row) => ({
        title: asString(row.title),
        description: asString(row.description),
        color: asString(row.color, "slate"),
      }))
      .filter((row) => row.title || row.description),
  [resolutionsContent]);

  useEffect(() => {
    setExpandedYears((current) => current.length || !resolutionYears.length
      ? current
      : [resolutionYears[0].year]);
  }, [resolutionYears]);

  const handleView = (doc: LegalDocument, event: React.MouseEvent) => {
    event.preventDefault();
    event.stopPropagation();

    if (!doc.url || doc.url === "#") {
      alert(
        `View link for "${doc.title}" is not yet available. Please check back later.`,
      );
      return;
    }

    window.open(doc.url, "_blank", "noopener,noreferrer");
  };

  const handleDownload = async (doc: LegalDocument) => {
    setDownloadingDocumentId(doc.id);
    try {
      await downloadDocument({
        url: doc.url,
        title: doc.title,
        fileType: doc.fileType,
      });
    } catch (error) {
      console.error(error);
      alert(`The file for "${doc.title}" is not available for direct download.`);
    } finally {
      setDownloadingDocumentId(null);
    }
  };

  const handleCommitteeClick = (committee: Committee) => {
    setSelectedCommittee(committee);

    setSelectedDetailedCommittee(null);

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

  if (aboutLoadState === "loading") {
    return <div className="min-h-[50vh] bg-slate-50 px-4 py-20 text-center text-slate-600">Loading About RDC content...</div>;
  }

  if (aboutLoadState === "error" || !aboutCmsPage) {
    return (
      <div className="min-h-[50vh] bg-slate-50 px-4 py-20 text-center">
        <h1 className="text-2xl font-bold text-slate-900">About RDC content is temporarily unavailable</h1>
        <p className="mt-3 text-slate-600">Please refresh the page or try again later.</p>
      </div>
    );
  }

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
              {asString(asRecord(heroContent).title) || "Content not configured"}
            </h1>
            <p className="text-lg text-white/90 max-w-2xl mx-auto">
              {asString(asRecord(heroContent).subtitle)}
            </p>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 space-y-20">
        {/* Legal Basis Section */}
        <section>
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold text-slate-900 mb-4">
              {asString(asRecord(legalContent).title) || "Content not configured"}
            </h2>
            <p className="text-lg text-slate-600 max-w-2xl mx-auto">
              {asString(asRecord(legalContent).subtitle)}
            </p>
          </div>

          {/* Changed grid to 3 columns and centered */}
          {legalDocuments.length === 0 ? (
            <p className="rounded-xl border border-slate-200 bg-white p-6 text-center text-slate-600">No legal documents are currently published.</p>
          ) : <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 max-w-5xl mx-auto">
            {legalDocuments.map((doc) => (
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
                      type="button"
                      onClick={(e) => handleView(doc, e)}
                      disabled={!doc.url || doc.url === "#"}
                      className={`flex-1 px-4 py-3 text-center font-medium rounded-lg transition flex items-center justify-center gap-2 ${
                        !doc.url || doc.url === "#"
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
                    <button
                      type="button"
                      onClick={() => handleDownload(doc)}
                      disabled={
                        downloadingDocumentId === doc.id ||
                        !canDownloadDocument(doc.url)
                      }
                      className={`flex-1 px-4 py-3 text-center font-medium rounded-lg transition ${
                        downloadingDocumentId === doc.id || !canDownloadDocument(doc.url)
                          ? "bg-slate-200 text-slate-400 cursor-not-allowed"
                          : "bg-slate-100 hover:bg-slate-200 text-slate-700"
                      }`}
                      title={
                        canDownloadDocument(doc.url)
                          ? `Download ${doc.title}`
                          : "A direct download file has not been provided"
                      }
                    >
                      {downloadingDocumentId === doc.id
                        ? "Downloading..."
                        : canDownloadDocument(doc.url)
                          ? "Download"
                          : "Unavailable"}
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>}
        </section>

        {/* Committees Section */}
        <section>
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold text-slate-900 mb-4">
              {asString(asRecord(committeesContent).title) || "Content not configured"}
            </h2>
            <p className="text-lg text-slate-600 max-w-2xl mx-auto">
              {asString(asRecord(committeesContent).subtitle)}
            </p>
          </div>

          {committees.length === 0 ? (
            <p className="rounded-xl border border-slate-200 bg-white p-6 text-center text-slate-600">No committee details are currently published.</p>
          ) : <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-6">
            {committees.map((committee) => (
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
          </div>}

          {/* Info Note */}
          {committees.length > 0 && <div className="mt-10 text-center">
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
          </div>}
        </section>

        {/* Organizational Structure */}
        <section>
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold text-slate-900 mb-4">
              {asString(asRecord(organizationContent).title) || "Content not configured"}
            </h2>
            <p className="text-lg text-slate-600 max-w-2xl mx-auto">
              {asString(asRecord(organizationContent).subtitle)}
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
                  <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide">{organizationNode("chairperson").label}</div>
                  <div className="mt-2 text-lg font-bold text-slate-900">{organizationNode("chairperson").title}</div>
                  <div className="text-sm text-slate-500">{organizationNode("chairperson").subtitle}</div>
                </div>
                <div
                  onClick={() => setSelectedNode("vice-chair")}
                  className={`group cursor-pointer rounded-2xl border border-slate-200/70 bg-white/80 backdrop-blur px-6 py-5 shadow-sm transition-all hover:shadow-[0_18px_40px_-22px_rgba(37,99,235,0.55)] ${
                    selectedNode === "vice-chair" ? "shadow-lg ring-2 ring-blue-500/60" : "hover:shadow-lg"
                  }`}
                >
                  <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide">{organizationNode("vice-chair").label}</div>
                  <div className="mt-2 text-lg font-bold text-slate-900">{organizationNode("vice-chair").title}</div>
                  <div className="text-sm text-slate-500">{organizationNode("vice-chair").subtitle}</div>
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
                  <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide">{organizationNode("secretariat").label}</div>
                  <div className="mt-2 text-base font-semibold text-slate-900">{organizationNode("secretariat").title}</div>
                  <div className="text-sm text-slate-500">{organizationNode("secretariat").subtitle}</div>
                </div>
                <div className="rounded-2xl border border-blue-500/40 bg-gradient-to-br from-blue-600 to-blue-700 px-6 py-5 text-white shadow-lg hover:shadow-[0_20px_45px_-22px_rgba(37,99,235,0.65)] transition-shadow">
                  <div className="text-xs font-semibold uppercase tracking-wide text-white/80">{organizationNode("secretary").label}</div>
                  <div className="mt-2 text-lg font-bold">{organizationNode("secretary").title}</div>
                  <div className="text-sm text-white/80">{organizationNode("secretary").subtitle}</div>
                </div>
                <div
                  onClick={() => setSelectedNode("executive-committee")}
                  className={`cursor-pointer rounded-2xl border border-slate-200/70 bg-white/80 backdrop-blur px-5 py-4 shadow-sm transition-all hover:shadow-[0_16px_36px_-22px_rgba(15,23,42,0.45)] ${
                    selectedNode === "executive-committee" ? "shadow-lg ring-2 ring-blue-500/60" : "hover:shadow-lg"
                  }`}
                >
                  <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide">{organizationNode("executive-committee").label}</div>
                  <div className="mt-2 text-base font-semibold text-slate-900">{organizationNode("executive-committee").title}</div>
                  <div className="text-sm text-slate-500">{organizationNode("executive-committee").subtitle}</div>
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
                      {organizationNode("voting-members").title}
                    </div>
                    <div className="mt-3 space-y-2 text-sm text-slate-600">
                      {organizationNode("voting-members").items.map((item) => (
                        <div key={item} className="rounded-lg border border-slate-200/70 bg-white px-3 py-2">{item}</div>
                      ))}
                    </div>
                  </div>
                  <div>
                    <div
                      onClick={() => setSelectedNode("non-voting-members")}
                      className={`cursor-pointer rounded-xl bg-gradient-to-r from-blue-600 to-blue-700 text-white px-4 py-3 text-center font-semibold shadow-sm transition-all hover:shadow-[0_16px_36px_-22px_rgba(37,99,235,0.55)] ${
                        selectedNode === "non-voting-members" ? "shadow-lg ring-2 ring-blue-400/60" : ""
                      }`}
                    >
                      {organizationNode("non-voting-members").title}
                    </div>
                    <div className="mt-3 space-y-2 text-sm text-slate-600">
                      {organizationNode("non-voting-members").items.map((item) => (
                        <div key={item} className="rounded-lg border border-slate-200/70 bg-white px-3 py-2">{item}</div>
                      ))}
                    </div>
                  </div>
                </div>
                <div className="mt-6 border-t border-dashed border-slate-300 pt-4 text-center">
                  <div className="rounded-xl bg-slate-800 text-white px-4 py-3 font-semibold">
                    {organizationNode("special-non-voting").title}
                  </div>
                  <div className="mt-2 text-xs text-slate-500">
                    {organizationNode("special-non-voting").subtitle}
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
                  <div className="text-xs font-semibold uppercase tracking-wide text-amber-700">{organizationNode("sectoral-committees").label}</div>
                  <div className="mt-2 text-base font-semibold text-slate-900">{organizationNode("sectoral-committees").title}</div>
                  <div className="mt-3 space-y-2 text-xs text-amber-900/80">
                    {organizationNode("sectoral-committees").items.map((item) => (
                      <div key={item} className="rounded-lg bg-white/80 px-3 py-2">{item}</div>
                    ))}
                  </div>
                </div>

                <div
                  onClick={() => setSelectedNode("special-committees")}
                  className={`cursor-pointer rounded-2xl border border-blue-200/60 bg-gradient-to-br from-blue-50 to-blue-100/60 px-5 py-4 shadow-sm transition-all hover:shadow-[0_16px_36px_-22px_rgba(37,99,235,0.45)] ${
                    selectedNode === "special-committees" ? "shadow-lg ring-2 ring-blue-400/60" : "hover:shadow-lg"
                  }`}
                >
                  <div className="text-xs font-semibold uppercase tracking-wide text-blue-700">{organizationNode("special-committees").label}</div>
                  <div className="mt-2 text-base font-semibold text-slate-900">{organizationNode("special-committees").title}</div>
                  <div className="mt-3 space-y-2 text-xs text-blue-900/80">
                    {organizationNode("special-committees").items.map((item) => (
                      <div key={item} className="rounded-lg bg-white/80 px-3 py-2">{item}</div>
                    ))}
                  </div>
                </div>

                <div
                  onClick={() => setSelectedNode("affiliate-committees")}
                  className={`cursor-pointer rounded-2xl border border-indigo-200/60 bg-gradient-to-br from-indigo-50 to-indigo-100/60 px-5 py-4 shadow-sm transition-all hover:shadow-[0_16px_36px_-22px_rgba(79,70,229,0.45)] ${
                    selectedNode === "affiliate-committees" ? "shadow-lg ring-2 ring-indigo-400/60" : "hover:shadow-lg"
                  }`}
                >
                  <div className="text-xs font-semibold uppercase tracking-wide text-indigo-700">{organizationNode("affiliate-committees").label}</div>
                  <div className="mt-2 text-base font-semibold text-slate-900">{organizationNode("affiliate-committees").title}</div>
                  <div className="mt-3 space-y-2 text-xs text-indigo-900/80">
                    {organizationNode("affiliate-committees").items.map((item) => (
                      <div key={item} className="rounded-lg bg-white/80 px-3 py-2">{item}</div>
                    ))}
                  </div>
                </div>

                <div className="rounded-2xl border border-slate-200/70 bg-white/80 backdrop-blur px-5 py-4 shadow-sm hover:shadow-[0_16px_36px_-22px_rgba(15,23,42,0.35)] transition-all">
                  <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">{organizationNode("advisory-committee").label}</div>
                  <div className="mt-2 text-base font-semibold text-slate-900">{organizationNode("advisory-committee").title}</div>
                  <div className="mt-3 rounded-lg bg-slate-100 px-3 py-2 text-xs text-slate-600">
                    {organizationNode("advisory-committee").subtitle}
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
              {asString(asRecord(resolutionsContent).title) || "Content not configured"}
            </h2>
            <p className="text-lg text-slate-600 max-w-2xl mx-auto">
              {asString(asRecord(resolutionsContent).subtitle)}
            </p>
          </div>

          <div className="bg-white rounded-3xl shadow-xl p-8 border border-slate-200">
            {/* Legend/Explanation */}
            <div className="mt-8 pt-6 border-t border-slate-200">
              <h4 className="font-semibold text-slate-900 mb-4">
                {asString(asRecord(resolutionsContent).legendTitle) || "Content not configured"}
              </h4>
              {resolutionLegendItems.length ? (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  {resolutionLegendItems.map((item, index) => (
                    <div key={`${item.label}-${index}`} className="flex items-center gap-2">
                      <div className={`h-3 w-3 rounded-full ${dotColorClass(item.color)}`} />
                      <span className="text-sm text-slate-600">{item.label}</span>
                    </div>
                  ))}
                </div>
              ) : <p className="text-sm text-slate-500">No document legend entries are published.</p>}
            </div>

            {/* Yearly Resolution Accordion */}
            <div className="space-y-4">
              {resolutionYears.length === 0 && (
                <p className="rounded-xl border border-slate-200 bg-slate-50 p-6 text-center text-slate-600">No resolution years are currently published.</p>
              )}
              {resolutionYears.map((yearData, index) => (
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
                            const resolutionTitle = resolution.title;
                            const isAdvisory =
                              resolutionTitle.includes("Advisory") ||
                              resolutionTitle.includes("Ad Referendum");
                            const isMMDA = resolutionTitle.includes("MMDA");
                            const isSectoral =
                              resolutionTitle.includes("Sectoral Committee");

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
                                    {resolution.number && resolution.number !== resolutionTitle && (
                                      <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">{resolution.number}</p>
                                    )}
                                    {resolution.url ? (
                                      <a
                                        href={resolution.url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="text-blue-700 hover:text-blue-900 hover:underline leading-relaxed"
                                      >
                                        {resolutionTitle}
                                      </a>
                                    ) : (
                                      <p className="text-slate-800 leading-relaxed">{resolutionTitle}</p>
                                    )}
                                    {resolution.description && (
                                      <p className="mt-2 text-sm leading-relaxed text-slate-600">{resolution.description}</p>
                                    )}
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
                                      {resolution.date && <span className="text-xs text-slate-500">Date: {resolution.date}</span>}
                                      {resolutionTitle.includes("Endorsing") && (
                                        <span className="text-xs text-green-600 bg-green-50 px-2 py-1 rounded">
                                          Endorsement
                                        </span>
                                      )}
                                      {resolutionTitle.includes("Approving") && (
                                        <span className="text-xs text-blue-600 bg-blue-50 px-2 py-1 rounded">
                                          Approval
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
                    {resolutionYears.length}
                  </div>
                  <div className="text-sm text-slate-600">Years Covered</div>
                </div>
                <div className="text-center">
                  <div className="text-3xl font-bold text-blue-700">
                    {resolutionYears.reduce(
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
                    {resolutionYears.length
                      ? Math.max(...resolutionYears.map((y) => y.content.length))
                      : 0}
                  </div>
                  <div className="text-sm text-slate-600">Most in a Year</div>
                </div>
                <div className="text-center">
                  <div className="text-3xl font-bold text-blue-700">
                    {resolutionDateRange}
                  </div>
                  <div className="text-sm text-slate-600">Date Range</div>
                </div>
              </div>
            </div>

            {/* Summary Stats */}
            <div className="mt-8 p-6 bg-slate-50 rounded-2xl">
              <h4 className="font-semibold text-slate-900 mb-3">
                {asString(asRecord(resolutionsContent).categoryTitle) || "Content not configured"}
              </h4>
              {resolutionCategoryItems.length ? (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  {resolutionCategoryItems.map((item, index) => (
                    <div key={`${item.title}-${index}`} className="text-center p-3 bg-white rounded-lg">
                      <div className={`text-lg font-bold ${textColorClass(item.color)}`}>{item.title}</div>
                      <div className="text-sm text-slate-600">{item.description}</div>
                    </div>
                  ))}
                </div>
              ) : <p className="text-sm text-slate-500">No resolution category summaries are published.</p>}
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
