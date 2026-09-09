type DownloadDocumentOptions = {
  url: string;
  title: string;
  fileType?: string;
};

const FILE_EXTENSION_PATTERN = /\.([a-z0-9]{1,10})$/i;

const toUrl = (value: string) => {
  if (typeof window === "undefined") return null;

  try {
    return new URL(value, window.location.href);
  } catch {
    return null;
  }
};

const googleDocumentExportUrl = (url: URL) => {
  const match = url.pathname.match(/^\/document\/d\/([^/]+)/i);
  if (url.hostname !== "docs.google.com" || !match) return null;
  return `https://docs.google.com/document/d/${match[1]}/export?format=pdf`;
};

const directDownloadUrl = (value: string) => {
  const url = toUrl(value);
  if (!url) return value;
  return googleDocumentExportUrl(url) || url.toString();
};

const extensionFromUrl = (value: string) => {
  const url = toUrl(value);
  const match = url?.pathname.match(FILE_EXTENSION_PATTERN);
  return match?.[1]?.toLowerCase() || "";
};

const extensionFromType = (fileType = "") => {
  const normalized = fileType.trim().toLowerCase();
  if (!normalized) return "";
  if (normalized === "jpeg") return "jpg";
  return /^(pdf|docx?|xlsx?|pptx?|csv|txt|rtf|odt|ods|odp|zip|jpg|png|gif|webp)$/.test(
    normalized,
  )
    ? normalized
    : "";
};

const downloadFileName = ({ url, title, fileType }: DownloadDocumentOptions) => {
  const extension = extensionFromUrl(url) || extensionFromType(fileType);
  const baseName =
    title
      .trim()
      .split("")
      .filter((character) => character.charCodeAt(0) >= 32)
      .join("")
      .replace(/[<>:"/\\|?*]/g, "")
      .replace(/\s+/g, " ")
      .replace(/[. ]+$/g, "") || "document";

  if (!extension || baseName.toLowerCase().endsWith(`.${extension}`)) return baseName;
  return `${baseName}.${extension}`;
};

const clickDownloadLink = (url: string, fileName: string, openInNewTab = false) => {
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  link.rel = "noopener noreferrer";
  if (openInNewTab) link.target = "_blank";
  document.body.appendChild(link);
  link.click();
  link.remove();
};

export const canDownloadDocument = (value: string) => {
  const url = toUrl(value);
  if (!url || value === "#") return false;
  if (url.hostname === "your-actual-link.com") return false;
  if (googleDocumentExportUrl(url)) return true;
  if (/fliphtml5\.com$/i.test(url.hostname) && !FILE_EXTENSION_PATTERN.test(url.pathname)) {
    return false;
  }
  return ["http:", "https:", "blob:", "data:"].includes(url.protocol);
};

export const downloadDocument = async (options: DownloadDocumentOptions) => {
  const sourceUrl = directDownloadUrl(options.url);
  const parsedUrl = toUrl(sourceUrl);
  if (!parsedUrl || !canDownloadDocument(options.url)) {
    throw new Error("This card does not point to a downloadable file.");
  }

  const fileName = downloadFileName({ ...options, url: sourceUrl });

  if (parsedUrl.origin === window.location.origin) {
    clickDownloadLink(parsedUrl.toString(), fileName);
    return;
  }

  try {
    const response = await fetch(parsedUrl.toString(), { credentials: "omit" });
    if (!response.ok) throw new Error(`Download failed with status ${response.status}.`);

    const contentType = response.headers.get("content-type")?.toLowerCase() || "";
    if (contentType.includes("text/html")) {
      throw new Error("The remote address returned a web page instead of a file.");
    }

    const objectUrl = URL.createObjectURL(await response.blob());
    clickDownloadLink(objectUrl, fileName);
    window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1_000);
  } catch {
    // Some public file hosts block browser fetches but still download files
    // correctly when their URL is opened directly.
    clickDownloadLink(parsedUrl.toString(), fileName, true);
  }
};
