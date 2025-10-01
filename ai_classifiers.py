"""
ai_classifier.py
This module contains all the code that classfies anything as an AI skill
All the functions that help process and classify text
Keybert for word extraction
Spacy to allow for Natural Language Processing
facebook/bart-large-mnli model a zero shot classifier that uses Labels to classify text
"""

import re
from functools import lru_cache
import spacy
import torch
from keybert import KeyBERT
from transformers import pipeline
from utils import (
    is_english,
    is_year_or_numeric,
    remove_substring_phrases,
    split_chunks,
    split_into_sentences,
)

nlp = spacy.load("en_core_web_sm")

# Use a zero-shot classifier
DEVICE = 0 if torch.cuda.is_available() else -1

classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli", device=DEVICE)

kw_model = KeyBERT()
# for is_ai_related()
AI_RELATED_THRESHOLD = 0.60
# for second_classification_check()
AI_SKILL_MIN_CONFIDENCE = 0.15
# immediate-accept override
OVERRIDE_HIGH_CONFIDENCE = 0.99

AI_RELATED_LABELS = ("Artificial Intelligence", "Not AI")

candidate_labels = [
    # Positive
    "AI skill",
    # Negative Labels
    # Engineering & Physical Sciences
    "Computer science concept",
    "Mathematics concept",
    "Civil engineering method",
    "Mechanical engineering method",
    "Electronic/electrical engineering method",
    "Chemical engineering method",
    "Physics research method",
    "Materials‑science method",
    "Analytical chemistry method",
    "Chemical synthesis technique",
    "Process engineering method",
    "Astronomy Concepts",
    # Biological Sciences & Medicine/Health
    "Biology research method",
    "Molecular biology technique",
    "Cellular biology method",
    "Biomedical research method",
    "Pharmaceutical research method",
    "Genetics technique",
    "Bioinformatics method",
    "Medical research method",
    "Dental research method",
    "Psychology research topic",
    "Healthcare research method",
    # Environment
    "Environmental science topic",
    "Transport studies topic",
    "Earth science method",
    "Geography topic",
    "Food science method",
    "Nutrition research method",
    # Business
    "Accounting & finance topic",
    "Economics topic",
    "Management & organisations topic",
    "Marketing topic",
    "International business topic",
    "Analytics & operations topic",
    "People, work & employment topic",
    # Social Sciences & Humanities
    "History research",
    "Archaeology/medieval studies topic",
    "Languages & cultural studies topic",
    "Literary studies topic",
    "Design methodology",
    "Fine art / art history topic",
    "Media & communication studies topic",
    "Musicology / performance studies topic",
    "Philosophy & religion topic",
    "Ethics research",
    "Education research method",
    "Law topic",
    "Politics & international studies topic",
    "Sociology & social policy topic",
    # Generic statements
    "Generic research",
    "Misc",
]


# Cache code was provided by ChatGPT after quering about ways to improve performance
@lru_cache(maxsize=10_000)
def _cached_zero_shot(text: str, labels: tuple[str, ...]):
    # labels is a tuple, so it's hashable
    return classifier(text, list(labels))


# 2) public wrapper: accept list or tuple, convert to tuple
def cached_zero_shot(text: str, labels):
    return _cached_zero_shot(text, tuple(labels))


def classify_ai(text: str, threshold: float = AI_RELATED_THRESHOLD):
    """
    Zero‑shot classify `text` as "Artificial Intelligence" vs "Not AI",
    then return (is_ai, ai_confidence).

    is_ai is True if the AI label’s score ≥ threshold.
    ai_confidence is the raw score for "Artificial Intelligence" (or 0.0).
    """
    if not text or not text.strip():
        return False, 0.0
        # 1) do the zero‑shot call

    result = cached_zero_shot(text, AI_RELATED_LABELS)

    # 2) extract the AI score
    try:
        ai_idx = result["labels"].index("Artificial Intelligence")
        ai_score = result["scores"][ai_idx]
    except ValueError:
        ai_score = 0.0

    # 3) check against threshold
    is_ai = ai_score >= threshold
    return is_ai, ai_score


def clean_text(text: str) -> str:
    # Insert spaces if letters and numbers are concatenated
    text = re.sub(r"([a-zA-Z])(\d)", r"\1 \2", text)
    text = re.sub(r"(\d)([a-zA-Z])", r"\1 \2", text)
    # Use SpaCy to remove tokens identified as dates or numbers if they dominate the text
    doc = nlp(text)
    if sum(1 for token in doc if token.like_num) > len(doc) / 2:
        return ""
    return text.strip()


def second_classification_check(phrase: str, *, min_score: float = AI_SKILL_MIN_CONFIDENCE):
    """
    2nd zero-shot classification with multiple negative labels.
    We only keep the phrase if the top label is 'AI skill'
    """
    if not phrase.strip():
        return False

    result = cached_zero_shot(phrase, tuple(candidate_labels))
    labels, scores = result["labels"], result["scores"]
    # Find and threshold the "AI skill" score
    if "AI skill" in labels:
        ai_idx = labels.index("AI skill")
        return scores[ai_idx] >= min_score

    return False


def refine_phrases(phrases, threshold: float = AI_RELATED_THRESHOLD):
    refined = []

    for raw in phrases:
        ph = clean_text(raw)
        if not ph:
            continue

        ph = " ".join(t.text for t in nlp(ph)).strip()
        if not ph or not is_english(ph):
            continue

        is_ai, p_ai = classify_ai(ph, threshold=threshold)

        # immediate override
        if p_ai >= OVERRIDE_HIGH_CONFIDENCE:               
            refined.append(ph)
            continue

        # must pass Stage 1
        if not is_ai:                                    
            continue

        # must pass Stage 2
        if not second_classification_check(
                ph, min_score=AI_SKILL_MIN_CONFIDENCE):   
            continue

        refined.append(ph)

    return remove_substring_phrases(refined)


def extract_key_phrases(text: str, top_n: int = 5):
    """
    Use KeyBERT to extract top keyphrases, then refine them
    with the zero-shot pipeline.
    """
    if not text.strip():
        return []
    keywords_with_scores = kw_model.extract_keywords(
        text,
        top_n=top_n,
        keyphrase_ngram_range=(1, 4),
        stop_words="english",
        # Maximal Marginal Relevance” mode that remove too similar phrases
        use_mmr=True,
        diversity=0.3,
    )
    raw_phrases = [kw for kw, _ in keywords_with_scores]
    return refine_phrases(raw_phrases)


def filter_ai_interests(interests_list, threshold: float = AI_RELATED_THRESHOLD):
    ai_interests = []
    for intr in interests_list:
        intr_clean = intr.strip()
        if not intr_clean:
            continue

        # two‑stage pass flag
        passed = False

        for chunk in split_chunks(intr_clean):
            is_ai, p_ai = classify_ai(chunk, threshold=threshold)

            # immediate override
            if p_ai >= OVERRIDE_HIGH_CONFIDENCE:
                passed = True
                break

            # must pass Stage 1
            if not is_ai:
                continue

            # must pass Stage 2
            if not second_classification_check(chunk, min_score=AI_SKILL_MIN_CONFIDENCE):
                continue

            passed = True
            break

        if not passed:
            continue

        # at least one chunk passed both stages
        skills = extract_key_phrases(intr_clean) or [intr_clean]
        ai_interests.append({
            "interest_text": intr_clean,
            "skills": skills
        })

    return ai_interests

def filter_ai_paragraphs(paragraphs, threshold=AI_RELATED_THRESHOLD):
    ai_sentences = []
    for para in paragraphs:
        for sent in split_into_sentences(para):
            if is_year_or_numeric(sent) or not is_english(sent):
                continue

            # reset for *this* sentence
            sentence_passed = False

            for chunk in split_chunks(sent):
                is_ai, p_ai = classify_ai(chunk, threshold=threshold)

                # immediate override
                if p_ai >= OVERRIDE_HIGH_CONFIDENCE:
                    sentence_passed = True
                    break

                # must pass Stage 1
                if not is_ai:
                    continue

                # must pass Stage 2
                if not second_classification_check(chunk, min_score=AI_SKILL_MIN_CONFIDENCE):
                    continue

                sentence_passed = True
                break

            if not sentence_passed:
                continue

            # at least one chunk truly passed both stages
            skills = extract_key_phrases(sent)
            if not skills:
                # no high‑level phrases, so skip entirely
                continue

            ai_sentences.append({
                "paragraph_text": sent,
                "skills": skills
            })

    return ai_sentences


def filter_ai_publications(publications, threshold: float = AI_RELATED_THRESHOLD):
    ai_pubs = []
    for pub in publications:
        title = (pub.get("title") or "").strip()
        if not title:
            continue

        # Will collect skills only if AT LEAST one chunk passes both stages
        sent_skills = []

        # Split the title into sentences/chunks
        for sent in split_into_sentences(title):
            if is_year_or_numeric(sent) or not is_english(sent):
                continue

            # Reset for each sentence
            sentence_passed = False

            for chunk in split_chunks(sent):
                is_ai, p_ai = classify_ai(chunk, threshold=threshold)

                # 1) immediate override
                if p_ai >= OVERRIDE_HIGH_CONFIDENCE:
                    sentence_passed = True
                    break

                #must pass Stage 1
                if not is_ai:
                    continue

                # must pass Stage 2
                if not second_classification_check(chunk, min_score=AI_SKILL_MIN_CONFIDENCE):
                    continue

                sentence_passed = True
                break

            if not sentence_passed:
                continue

            # Only extract phrases if one of the chunks actually passed
            skills = extract_key_phrases(sent)
            if skills:
                sent_skills.extend(skills)

        if sent_skills:
            pub["skills"] = list(set(sent_skills))
            ai_pubs.append(pub)

    return ai_pubs



def combine_all_ai_skills(ai_interests=None, ai_publications=None, ai_paragraphs=None):
    """
    Mix out the extracted skill phrases from:
      - AI interests
      - AI publications
      - AI paragraphs
    into a single set, then convert to list.
    """
    combined_skills = set()

    # if any of these is None, treat it as an empty list
    for i in ai_interests or []:
        for skill in i.get("skills", []):
            combined_skills.add(skill)

    for p in ai_publications or []:
        for skill in p.get("skills", []):
            combined_skills.add(skill)

    for pr in ai_paragraphs or []:
        for skill in pr.get("skills", []):
            combined_skills.add(skill)

    return list(combined_skills)
