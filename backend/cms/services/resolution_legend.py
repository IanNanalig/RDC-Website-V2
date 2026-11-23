from copy import deepcopy

from rest_framework.exceptions import ValidationError


def legend_key(entry):
    return str(entry.get("key") or str(entry.get("label") or "").strip().lower()).strip()


def legend_entries(content):
    return {
        legend_key(entry): {**entry, "key": legend_key(entry)}
        for entry in content.get("legendItems") or []
        if isinstance(entry, dict) and str(entry.get("label") or "").strip()
    }


def resolve_type(row, entries):
    """Resolve a saved key or a legacy display value without guessing between types."""
    if "resolutionTypeKey" in row:
        key = row["resolutionTypeKey"]
        return key if isinstance(key, str) and key in entries else None
    legacy = row.get("legendItems") or []
    if not isinstance(legacy, list):
        return None
    if legacy:
        keys = set()
        for entry in legacy:
            if not isinstance(entry, dict):
                return None
            key = legend_key(entry)
            if key not in entries:
                label = str(entry.get("label") or "").strip().lower()
                matches = [candidate for candidate, value in entries.items() if value["label"].strip().lower() == label]
                if entry.get("key") or len(matches) != 1:
                    return None
                key = matches[0]
            keys.add(key)
        return next(iter(keys)) if len(keys) == 1 else None
    title = str(row.get("title") or row.get("name") or "")
    if "Advisory" in title or "Ad Referendum" in title:
        label = "Advisory/Referendum"
    elif "MMDA" in title:
        label = "MMDA Resolution"
    elif "Sectoral Committee" in title:
        label = "Sectoral Committee"
    else:
        label = "RDC Resolution"
    return resolve_type({"legendItems": [{"label": label}]}, entries)


RESOLUTION_ROW_KEYS = ("resolutions", "items", "documents", "content")


def resolution_year_rows(group):
    rows = [(key, group[key]) for key in RESOLUTION_ROW_KEYS if isinstance(group.get(key), list)]
    return next(((key, values) for key, values in rows if values), rows[0] if rows else ("resolutions", []))


def _row(value):
    return value if isinstance(value, dict) else {"title": value}


def _identity(group, row):
    return ("id", str(row["id"])) if row.get("id") else (
        "legacy", str(group.get("year") or ""), row.get("title") or row.get("number") or "",
    )


def resolution_entries(content):
    for group in content.get("years") or []:
        if isinstance(group, dict):
            for item in resolution_year_rows(group)[1]:
                if isinstance(item, (dict, str)):
                    yield group, _row(item)


def validate_resolution_types(content, previous):
    """Persist one stable type per resolution while retaining private legacy information."""
    content = deepcopy(content)
    if "legendItems" not in content:
        content["legendItems"] = deepcopy(previous.get("legendItems", []))
    configured = content.get("legendItems")
    if not isinstance(configured, list) or any(
        not isinstance(entry, dict) or not isinstance(entry.get("label"), str) or not entry["label"].strip()
        for entry in configured
    ):
        raise ValidationError({"legendItems": "Each document legend entry needs a label."})
    entries = legend_entries(content)
    if len(entries) != len(configured):
        raise ValidationError({"legendItems": "Document legend identifiers must be unique."})
    content["legendItems"] = list(entries.values())
    old_rows = {_identity(group, row): row for group, row in resolution_entries(previous)}
    previous_entries = legend_entries(previous)
    errors = {}
    for year_index, group in enumerate(content.get("years") or []):
        if not isinstance(group, dict):
            raise ValidationError({"years": "Each resolution year must be an object."})
        if sum(bool(group.get(key)) for key in RESOLUTION_ROW_KEYS) > 1:
            raise ValidationError({f"years.{year_index}": "Submit one resolution list per year."})
        key, rows = resolution_year_rows(group)
        for row_index, value in enumerate(rows):
            row = _row(value)
            old = old_rows.get(_identity(group, row))
            proposed = row.get("legendItems", [])
            previous_legacy = old.get("legendItems", []) if old else []
            path = f"years.{year_index}.{key}.{row_index}.resolutionTypeKey"
            if {"resolutionTypeKeys", "resolution_type_keys", "resolution_type_key"}.intersection(row):
                errors[path] = "Submit one resolutionTypeKey."
                continue
            if not isinstance(proposed, list) or (len(proposed) > 1 and (old is None or proposed != previous_legacy)):
                errors[path] = "Select exactly one Resolution Type."
                continue
            if "resolutionTypeKey" in row:
                selected = resolve_type(row, entries)
                if len(proposed) == 1 and proposed != previous_legacy:
                    if resolve_type({"legendItems": proposed}, entries) != selected:
                        errors[path] = "Submit one matching Resolution Type."
                        continue
            elif proposed and proposed != previous_legacy:
                selected = resolve_type(row, entries)
            else:
                selected = resolve_type(old, previous_entries) if old else None
            if selected not in entries:
                errors[path] = "Choose one configured Resolution Type for this resolution."
                continue
            if isinstance(value, str):
                # Keep old text-only records in their existing representation
                # until an editor explicitly changes the record.
                continue
            normalized = {k: v for k, v in row.items() if k not in {"legendTitle", "legendItems", "legacyResolutionLegend"}}
            if old:
                private = old.get("legacyResolutionLegend") or {
                    name: deepcopy(old[name]) for name in ("legendTitle", "legendItems")
                    if old.get(name) and (name == "legendTitle" or "resolutionTypeKey" not in old)
                }
                if private:
                    normalized["legacyResolutionLegend"] = private
            rows[row_index] = {
                **normalized, "resolutionTypeKey": selected, "legendItems": [entries[selected]],
            }
        for alias in RESOLUTION_ROW_KEYS[1:]:
            group.pop(alias, None)
        group["resolutions"] = rows
    if errors:
        raise ValidationError(errors)
    return content


def public_resolution_types(content):
    entries = legend_entries(content)
    for group in content.get("years") or []:
        if not isinstance(group, dict):
            continue
        _, rows = resolution_year_rows(group)
        for index, value in enumerate(rows):
            if not isinstance(value, (dict, str)):
                continue
            row = _row(value)
            selected = resolve_type(row, entries)
            row.pop("legendTitle", None)
            row.pop("legacyResolutionLegend", None)
            row["resolutionTypeKey"] = selected
            row["legendItems"] = [entries[selected]] if selected else []
            rows[index] = row
    return content
