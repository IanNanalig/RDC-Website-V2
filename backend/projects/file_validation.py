import io
import zipfile


ALLOWED_EVIDENCE_EXTENSIONS = {"pdf", "docx", "xlsx", "csv", "png", "jpg", "jpeg"}


def validate_uploaded_document(filename, content_type, data, extension):
    """Return a canonical MIME type after bounded signature/content validation."""
    extension = str(extension or "").strip().lower().lstrip(".")
    if extension == "pdf":
        valid = data.startswith(b"%PDF-")
        canonical = "application/pdf"
    elif extension == "png":
        valid = data.startswith(b"\x89PNG\r\n\x1a\n")
        canonical = "image/png"
    elif extension in {"jpg", "jpeg"}:
        valid = data.startswith(b"\xff\xd8\xff")
        canonical = "image/jpeg"
    elif extension in {"docx", "xlsx"}:
        valid = False
        canonical = (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            if extension == "docx"
            else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                entries = archive.infolist()
                names = {item.filename for item in entries}
                valid = "[Content_Types].xml" in names and any(
                    value.startswith("word/" if extension == "docx" else "xl/") for value in names
                )
                expanded_size = sum(item.file_size for item in entries)
                unsafe_path = any(
                    item.filename.startswith(("/", "\\")) or ".." in item.filename.replace("\\", "/").split("/")
                    for item in entries
                )
                encrypted = any(item.flag_bits & 0x1 for item in entries)
                suspicious_ratio = expanded_size > max(len(data) * 100, 20 * 1024 * 1024)
                if len(entries) > 20000 or expanded_size > 200 * 1024 * 1024 or suspicious_ratio or unsafe_path or encrypted:
                    valid = False
        except (zipfile.BadZipFile, OSError, ValueError):
            valid = False
    elif extension == "csv":
        canonical = "text/csv"
        valid = b"\x00" not in data
        if valid:
            try:
                data.decode("utf-8-sig")
            except UnicodeDecodeError:
                try:
                    data.decode("cp1252")
                except UnicodeDecodeError:
                    valid = False
    else:
        valid = False
        canonical = str(content_type or "application/octet-stream")
    if not valid:
        raise ValueError(f"{filename} does not match its .{extension} file type or is corrupt.")
    return canonical
