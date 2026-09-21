import math
import re
from collections import Counter


STOP_WORDS = {
    "and", "are", "for", "from", "has", "have", "into", "its", "not", "of", "on", "or",
    "project", "program", "the", "this", "to", "was", "were", "will", "with",
}


def tokenize(value):
    return [
        token
        for token in re.findall(r"[a-z0-9]+", str(value or "").lower())
        if len(token) >= 3 and token not in STOP_WORDS
    ]


def _tfidf_vectors(query_text, records):
    documents = [tokenize(record.normalized_text) for record in records]
    query = tokenize(query_text)
    all_documents = documents + [query]
    document_count = max(1, len(all_documents))
    frequencies = [Counter(tokens) for tokens in all_documents]
    document_frequency = Counter()
    for tokens in all_documents:
        document_frequency.update(set(tokens))

    def vector(counter):
        total = max(1, sum(counter.values()))
        return {
            token: (count / total) * (math.log((1 + document_count) / (1 + document_frequency[token])) + 1.0)
            for token, count in counter.items()
        }

    return vector(frequencies[-1]), [vector(item) for item in frequencies[:-1]]


def _cosine(left, right):
    if not left or not right:
        return 0.0
    dot = sum(value * right.get(key, 0.0) for key, value in left.items())
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0


def find_similar_projects(query_features, records, limit=3):
    records = list(records)
    if not records:
        return []
    query_text = str(query_features.get("text") or "")
    query_vector, record_vectors = _tfidf_vectors(query_text, records)
    query_context = query_features.get("context") if isinstance(query_features.get("context"), dict) else {}
    matches = []
    for record, vector in zip(records, record_vectors):
        score = _cosine(query_vector, vector)
        context = record.feature_snapshot.get("context") if isinstance(record.feature_snapshot, dict) else {}
        context = context if isinstance(context, dict) else {}
        shared = sorted(
            set(tokenize(query_text)).intersection(tokenize(record.normalized_text)),
            key=lambda token: query_vector.get(token, 0) * vector.get(token, 0),
            reverse=True,
        )[:8]
        if query_context.get("sector") and query_context.get("sector") == context.get("sector"):
            score = min(1.0, score + 0.05)
            shared.insert(0, f"Same sector: {query_context['sector'].replace('_', ' ').title()}")
        if query_context.get("agency") and str(query_context.get("agency")).casefold() == str(context.get("agency")).casefold():
            score = min(1.0, score + 0.03)
            shared.insert(0, f"Same agency: {query_context['agency']}")
        matches.append({"record": record, "score": score, "shared_features": shared[:10]})
    matches.sort(key=lambda item: (-item["score"], -item["record"].id))
    return [item for item in matches[:limit] if item["score"] > 0]
