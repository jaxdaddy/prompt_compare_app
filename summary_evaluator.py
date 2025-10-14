"""
Module: summary_evaluator
Purpose: Automatically evaluate Eumonics summary reports for relevance and readability.
Author: Shan McAdoo (with ChatGPT)
Date: 2025-10-13
"""

import re
from typing import Dict, Tuple
from collections import Counter


# ----------------------------------------------------------
# Core Evaluation Functions
# ----------------------------------------------------------

def count_occurrences(text: str, terms: list) -> int:
    """Counts how many of the terms appear in the text."""
    return sum(1 for term in terms if re.search(rf"\b{term}\b", text, re.IGNORECASE))


# ----------------------------------------------------------
# Scoring Metrics
# ----------------------------------------------------------

def score_metric_alignment(text: str) -> Tuple[int, str]:
    """Score 0–5: Are PPCC metrics used correctly and consistently?"""
    metrics = ["COR", "COY", "POR", "POY"]
    found = count_occurrences(text, metrics)
    if found == 4:
        score = 5
        note = "All PPCC metrics used consistently."
    elif found >= 2:
        score = 3
        note = "Partial metric coverage (some PPCC metrics missing)."
    else:
        score = 1
        note = "Few or no PPCC metrics found."
    return score, note


def score_data_relevance(text: str) -> Tuple[int, str]:
    """Score 0–5: Are stock movements supported by quantitative or news-based data?"""
    patterns = ["%","news","correlation","sentiment","Net Change","article"]
    count = count_occurrences(text, patterns)
    if count >= 10:
        return 5, "Strong quantitative and news-based justification."
    elif count >= 5:
        return 4, "Moderate coverage of data-driven explanations."
    elif count >= 3:
        return 3, "Partial data context present."
    else:
        return 1, "Weak or missing data-based explanations."


def score_consistency_with_primer(text: str) -> Tuple[int, str]:
    """Score 0–5: Are sentiment and PPCC metrics logically aligned?"""
    bullish_patterns = re.findall(r"bullish|positive|optimistic", text, re.IGNORECASE)
    bearish_patterns = re.findall(r"bearish|negative|pessimistic", text, re.IGNORECASE)
    if bullish_patterns and bearish_patterns:
        return 5, "Consistent bullish/bearish context detected."
    elif bullish_patterns or bearish_patterns:
        return 3, "Partial sentiment linkage."
    else:
        return 1, "No clear sentiment alignment found."


def score_structure(text: str) -> Tuple[int, str]:
    """Score 0–5: Clear organization of sections."""
    headers = ["Quantitative Analysis", "Key Drivers", "Momentum", "Sentiment", "Correlation", "Summary"]
    found = count_occurrences(text, headers)
    if found >= 5:
        return 5, "Excellent structure with clear sections."
    elif found >= 3:
        return 4, "Mostly well-structured."
    elif found >= 2:
        return 3, "Some structure detected."
    else:
        return 1, "Unstructured text."


def score_clarity(text: str) -> Tuple[int, str]:
    """Score 0–5: Evaluate clarity and accessibility."""
    avg_sentence_len = sum(len(s.split()) for s in re.split(r'[.!?]', text) if s.strip()) / max(1, len(re.split(r'[.!?]', text)))
    if avg_sentence_len < 22:
        return 5, "Clear and concise language."
    elif avg_sentence_len < 28:
        return 4, "Readable with minor complexity."
    elif avg_sentence_len < 35:
        return 3, "Dense but understandable."
    else:
        return 1, "Verbose or unclear writing."


def score_writing_quality(text: str) -> Tuple[int, str]:
    """Score 0–5: Evaluate writing tone and redundancy."""
    redundancy = len(re.findall(r"\b(the the|and and|of of|to to)\b", text, re.IGNORECASE))
    if redundancy == 0:
        return 5, "Strong and consistent writing quality."
    elif redundancy < 3:
        return 4, "Minor redundancies."
    else:
        return 2, "Frequent repetition or inconsistencies."


# ----------------------------------------------------------
# Composite Scoring
# ----------------------------------------------------------

def evaluate_summary_text(text: str) -> Dict[str, Dict]:
    """Compute relevance and readability scores for a given text."""
    # Relevance scores
    metric_score = score_metric_alignment(text)
    data_score = score_data_relevance(text)
    primer_score = score_consistency_with_primer(text)

    # Readability scores
    structure_score = score_structure(text)
    clarity_score = score_clarity(text)
    writing_score = score_writing_quality(text)

    relevance_total = sum([metric_score[0], data_score[0], primer_score[0]])
    readability_total = sum([structure_score[0], clarity_score[0], writing_score[0]])

    weighted_total = (relevance_total / 15 * 0.6 + readability_total / 15 * 0.4) * 100

    return {
        "relevance": {
            "Metric Alignment": metric_score,
            "Data Relevance": data_score,
            "Primer Consistency": primer_score,
            "Total": relevance_total
        },
        "readability": {
            "Structure": structure_score,
            "Clarity": clarity_score,
            "Writing Quality": writing_score,
            "Total": readability_total
        },
        "composite_score": round(weighted_total, 2)
    }
