"""
utils.py
This module contains utility functions 
Functions to facilitate the processing of text that are called in multiple steps
Both during scraping and while filtering for AI skills
"""
import random
import re
import spacy
from langdetect import detect

nlp = spacy.load("en_core_web_sm", disable=["ner", "tagger", "lemmatizer"])
USE_SPACY = True
LEEDS_PHRASES = ("university of leeds", "leeds university")
HONOURS = (
    "obe", "cbe", "mbe", "frs", "frse", "freeng", "freng",
    "fmedsci", "facss", "dphil", "phd", "dsc", "frsa","ficheme", "ceng"
    "ieng","amrsc","amicheme","mimmm","frms","lrps","CMBE","FRSA",
    "FHEA", "FCMI","CMgr","CFCIPD","MA"
)

def is_english(text: str) -> bool:
    """
    Checks if sentence is written in english
    """
    if not text:
        return False
    # Assume english for short strings to avoid losings words such as AI
    if len(text.split()) < 3:
        return True
    try:
        return detect(text) == "en"
    except Exception:
        return False

def split_into_sentences(text: str) -> list[str]:
    """
    Return a list of non‑empty, trimmed sentences.
    """
    sentences = []
    for sent in nlp(text).sents:
        s = sent.text.strip()
        if s:
            sentences.append(s)
    return sentences

def split_chunks(sentence: str) -> list[str]:
    """
    Breaks a sentence into smaller bits on semicolons, parentheses.
    """
    # 1) split on the delimiters
    raw_chunks = re.split(r"[;()]+", sentence)

    # 2) strip whitespace and filter out empty strings
    cleaned_chunks = []
    for chunk in raw_chunks:
        chunk = chunk.strip()
        if chunk:
            cleaned_chunks.append(chunk)

    return cleaned_chunks

def is_year_or_numeric(phrase: str) -> bool:
    """
    Helper to skip years or numeric references.
    """
    cleaned = phrase.lower().strip()
    # If it has 4 consecutive digits or is purely numeric, skip
    if re.search(r"\d{4}", cleaned):
        return True
    if cleaned.isdigit():
        return True
    return False

def remove_substring_phrases(phrases):
    """
    If we have both 'deep learning' and 'deep learning methods',
    and the shorter is entirely contained in the longer, remove duplicates.
    """
    phrases_sorted = sorted(set(phrases), key=len, reverse=True)
    final = []
    for p in phrases_sorted:
        # if p is a substring of any phrase we already kept, skip it
        if any(p in kept for kept in final):
            continue
        final.append(p)
    return final

def is_blocked(html_text: str):
    """
    Check if page is blocked or CAPTCHA is required using multiple indicators.
    """
    # Existing checks
    if ("Please show you're not a robot" in html_text) or \
       ("unusual traffic" in html_text) or \
       ("systems have detected unusual traffic" in html_text): # Added variation
        return True

    # Check common block page titles (case-insensitive)
    lower_text = html_text.lower()
    if "<title>sorry..." in lower_text or \
       "<title>error" in lower_text or \
       "<title>about this page" in lower_text:
        return True

    # Check for reCAPTCHA elements
    if 'grecaptcha' in html_text or 'recaptcha.google.com' in html_text:
        return True

    return False
def clean_full_name(full_name: str) -> str:
    """
    Clean name so that there are no issues when searching on Google Scholar.
    Removes credentials and common academic prefixes.
    AND common post-nominals / honours.
    """
    # drop anything after a comma first
    name_part = full_name.split(",")[0]

    # drop titles
    name_part = re.sub(r"^(professor|prof\.?|dr\.?)\s+", "",
                       name_part, flags=re.IGNORECASE)

    # drop trailing honours
    pattern = r"\b(" + "|".join(HONOURS) + r")\.?\b"
    name_part = re.sub(pattern, "", name_part, flags=re.IGNORECASE)

    # collapse whitespace
    return re.sub(r"\s{2,}", " ", name_part).strip()

def build_author_query(name: str):
    """
    Create Google Scholar query using the clean name.
    """
    clean_name = clean_full_name(name)
    query = f'("University of Leeds" OR "Leeds University") "{clean_name}"'
    return {"view_op": "search_authors", "hl": "en", "mauthors": query}

def is_leeds_affiliation(text: str) -> bool:
    """
    Ensure it looks for lecturers only at University of Leeds
    """
    text = (text or "").lower()
    return any(p in text for p in LEEDS_PHRASES)


def select_proxy_and_headers():
    """
    Randomly select a user-agent and proxy for requests.
    """
    user_agent = [
    # Chrome / Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.6367.91 Safari/537.36",

    # Chrome / macOS (Apple Silicon)
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.6367.91 Safari/537.36",

    # Firefox / Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",

    # Edge / Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.6367.91 Safari/537.36 Edg/124.0.2478.51",

    # Safari / macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",

    # Chrome / Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.6367.91 Safari/537.36",

    # Chrome Mobile / Android
    "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.6367.91 Mobile Safari/537.36",

    # Safari / iPhone
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",

    # Samsung Internet / Android
    "Mozilla/5.0 (Linux; Android 14; SM-S921B) AppleWebKit/537.36 "
    "(KHTML, like Gecko) SamsungBrowser/24.0 Chrome/114.0.0.0 Mobile Safari/537.36",

    # Brave / Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.6367.91 Safari/537.36 Brave/1.66.109",
    ]
    proxies = [
        # Could be added
    ]
    headers = {"User-Agent": random.choice(user_agent)}
    proxy = None
    if proxies:
        proxy_choice = random.choice(proxies)
        proxy = {"http": proxy_choice, "https": proxy_choice}
    return headers, proxy

def name_key(full_name: str) -> str:

    nm = clean_full_name(full_name)
    parts = [p.lower() for p in re.split(r"\s+", nm) if p]
    if len(parts) < 2:
        return ""
    first, last = parts[0], parts[-1]
    return f"{last}|{first[0]}"