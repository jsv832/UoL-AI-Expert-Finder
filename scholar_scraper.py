"""
scholar_scraper.py
This module scrapes through the Google Scholar of all the Leeds lecturers in a particular School
It will look for AI skills, Publication Titles or interests for the lecturer and save it on database
Information such as Scholar URL will be stored and a tag for any lecturer who has been scrapped
"""

import random
import time
import requests
import re
from bs4 import BeautifulSoup
from ai_classifiers import (
    AI_RELATED_THRESHOLD,
    combine_all_ai_skills,
    filter_ai_interests,
    filter_ai_publications,
)
from department import SCHOOL_DATA
from utils import (
    build_author_query,
    is_blocked,
    select_proxy_and_headers,
    is_leeds_affiliation,
    clean_full_name,
    name_key
    )
from database import get_lecturers_collection
from delta import (write_delta_report, list_delta, iso_now, safe_slug,normalize_interest_texts,extract_pub_titles)


def fetch_scholar_results(session: requests.Session, params: dict):
    """
    Hit the Google-Scholar author search with *params* and return the parsed
    results page (BeautifulSoup).  Raises RuntimeError if Google blocks us.
    """
    headers, proxy = select_proxy_and_headers()
    response = session.get(
        "https://scholar.google.com/citations",
        params=params,
        headers=headers,
        proxies=proxy,
        timeout=10,
    )
    if is_blocked(response.text):
        raise RuntimeError("Blocked by Google Scholar. Consider rotating IP/User-Agent.")
    return BeautifulSoup(response.text, "html.parser")


def find_scholar_profile(soup: BeautifulSoup, name: str):
    """
    From an author-search *soup*, locate the best-matching profile for *name*.
    Returns ``(profile_url, interests_list)`` or ``(None, [])``.
    """
    
    author_results = soup.select(".gs_ai_chpr")
    scholar_profile_url = None
    interests_list = []
    for result in author_results:
        prof_name_tag = result.select_one(".gs_ai_name a")
        prof_name = prof_name_tag.text if prof_name_tag else ""
        if prof_name.lower() == name.lower():
            scholar_profile_url = "https://scholar.google.com" + prof_name_tag["href"]
            interests_list = [i.text for i in result.select(".gs_ai_one_int")]
            break
    if not scholar_profile_url and author_results:
        # fallback: if we can't find an exact name match, take the first
        first = author_results[0]
        prof_name_tag = first.select_one(".gs_ai_name a")
        scholar_profile_url = "https://scholar.google.com" + prof_name_tag["href"]
        interests_list = [i.text for i in first.select(".gs_ai_one_int")]
    return scholar_profile_url, interests_list


def fetch_profile_details(session: requests.Session, profile_url: str):
    """
    Gets profile_url and return its BeautifulSoup representation.
    Raises a RuntimeError if Google blocks the request.
    """
    time.sleep(random.uniform(3, 6))
    headers, proxy = select_proxy_and_headers()
    response = session.get(profile_url, headers=headers, proxies=proxy, timeout=10)
    if is_blocked(response.text):
        raise RuntimeError("Blocked while accessing profile page.")
    soup_profile = BeautifulSoup(response.text, "html.parser")
    return soup_profile


def fetch_all_publications(session: requests.Session, soup_profile: BeautifulSoup, profile_url: str):
    """
    Collect every publication listed on the profile page and return:
    [{"title": str, "year": str, "authors": str}, ...]
    """
    publications = []

    def extract_rows(soup_obj):
        rows_local = []
        rows = soup_obj.select("tr.gsc_a_tr")
        for row in rows:
            title_tag = row.select_one("a.gsc_a_at")
            year_tag = row.select_one(".gsc_a_y .gsc_a_h, .gsc_a_y .gsc_a_hc, .gsc_a_y span")
            # authors: first '.gs_gray' inside the title cell
            title_cell = row.select_one("td.gsc_a_t")
            authors = ""
            if title_cell:
                gray = title_cell.select("div.gs_gray")
                if gray:
                    authors = gray[0].get_text(strip=True)

            title = title_tag.text if title_tag else ""
            year = year_tag.text if year_tag else ""
            if title:
                rows_local.append({"title": title.strip(), "year": year.strip(), "authors": authors})
        return rows_local

    publications.extend(extract_rows(soup_profile))

    show_more_button = soup_profile.select_one('#gsc_bpf_more')
    if show_more_button and not show_more_button.has_attr('disabled'):
        cstart = len(publications)
        pagesize = 100
        while True:
            paged_url = f"{profile_url}&cstart={cstart}&pagesize={pagesize}"
            time.sleep(random.uniform(3, 6))
            headers, proxy = select_proxy_and_headers()
            try:
                response_more = session.get(paged_url, headers=headers, proxies=proxy, timeout=10)
                response_more.raise_for_status()
            except requests.exceptions.RequestException as e:
                print(f"HTTP Error fetching more publications: {e}")
                break
            if is_blocked(response_more.text):
                print("Blocked while loading additional publications.")
                break
            soup_more = BeautifulSoup(response_more.text, "html.parser")
            new_rows = extract_rows(soup_more)
            if not new_rows:
                break
            publications.extend(new_rows)
            cstart += len(new_rows)
            if len(new_rows) < pagesize:
                break

    return publications


def parse_profile_interests(soup_profile: BeautifulSoup, interests_list: list):
    """
    Grab the "Interests" from the profile's top area (if any),
    and combine them with the interests we found from the search results page.
    """
    profile_interests = [tag.text for tag in soup_profile.select("#gsc_prf_int a")]
    for intr in profile_interests:
        if intr not in interests_list:
            interests_list.append(intr)
    return interests_list

def db_name_map(coll, exclude_id):
    """
    Map of name_key -> list of lecturers (handles homonyms).
    Skips the current lecturer.
    """
    m = {}
    for doc in coll.find({}, {"_id": 1, "name": 1, "profileUrl": 1}):
        if doc["_id"] == exclude_id:
            continue
        k = name_key(doc.get("name", "") or "")
        if not k:
            continue
        m.setdefault(k, []).append({
            "lecturer_id": doc["_id"],
            "name": doc.get("name", ""),
            "profileUrl": doc.get("profileUrl", ""),
        })
    return m

def process_lecturer_record(lecturer: dict, delta_collector):
    """
    Tries the stored/guessed Google-Scholar profile URL first.  
    If that request is blocked, falls back to a fresh author-search.  
    f the fallback is also blocked (or finds no profile), the lecturer
    is skipped and the scraper moves on.
    """
    name = lecturer.get("name")
    session = requests.Session()

    # Check if a Scholar URL already stored from the Leeds-page scrape
    scholar_profile_url = (lecturer.get("scholar_profile") or "").strip()
    came_from_staff_page = bool(scholar_profile_url)  
    interests_list: list[str] = []

    # If not, fall back to the Google-Scholar search as before
    if not scholar_profile_url:
        params = build_author_query(name)
        try:
            soup = fetch_scholar_results(session, params)
        except RuntimeError as block_exc:
            print(f"{block_exc} — for lecturer: {name}")
            return

        scholar_profile_url, interests_list = find_scholar_profile(soup, name)
        if not scholar_profile_url:
            print(f"No Google Scholar profile found for {name}.")
            return
        # ➡️ profile came from our own search, so we *do* need to verify it
        came_from_staff_page = False

    #Fetch the Scholar profile page
    try:
        soup_profile = fetch_profile_details(session, scholar_profile_url)
    except RuntimeError as block_exc:
        print(f"{block_exc} — for lecturer: {name}. Falling back to author search…")
        try:
            params = build_author_query(name)
            soup_search = fetch_scholar_results(session, params)            # may raise
            scholar_profile_url, interests_list = find_scholar_profile(soup_search, name)

            if not scholar_profile_url:
                print(f"No profile found for {name} after fallback search. Skipping.")
                return

            # second attempt with the new (or same) profile URL
            came_from_staff_page = False       # URL came from our own search
            soup_profile = fetch_profile_details(session, scholar_profile_url)  # may raise

        except RuntimeError as block_exc2:
            print(f"Fallback search also blocked for {name}: {block_exc2} – skipping.")
            return
        except Exception as exc2:
            print(f"Unexpected error during fallback for {name}: {exc2}")
            return

    # Enforce the Leeds-affiliation check if scraper discovered the
    # profile. When the URL was supplied by the staff page
    # trust it even if Google Scholar shows a different affiliation.
    if not came_from_staff_page:
        aff_full = soup_profile.select_one("#gsc_prf_i .gsc_prf_il")
        if not is_leeds_affiliation(aff_full.text if aff_full else ""):
            print(f"{name}: profile is not University of Leeds – skipped.")
            return

    publications = fetch_all_publications(session, soup_profile, scholar_profile_url)
    interests_list = parse_profile_interests(soup_profile, interests_list)

    # Filter down to AI-related interests and AI-related publications
    filtered_interests = filter_ai_interests(interests_list, threshold=0.75)
    filtered_publications = filter_ai_publications(publications, threshold=AI_RELATED_THRESHOLD)
    combined_skills = combine_all_ai_skills(filtered_interests, filtered_publications, None)
    is_ai_lecturer = bool(combined_skills)
    coll = get_lecturers_collection()
    name_map = db_name_map(coll, exclude_id=lecturer["_id"])
    collaborator_counts = {}

    for pub in publications:
        authors = (pub.get("authors") or "").strip()
        internal_matches = []
        if authors:
            seen_ids_this_pub = set()  # ensure count += 1 only once per pub per collaborator
            # Split "J Doe, A Smith and B Lee" into individuals
            for raw_author in re.split(r"\s*,\s*|\s+and\s+", authors):
                k = name_key(raw_author)
                if not k:
                    continue
                for match in name_map.get(k, []):
                    internal_matches.append(match)

                    lid = match["lecturer_id"]
                    entry = collaborator_counts.setdefault(
                        lid,
                        {
                            "name": match["name"],
                            "profileUrl": match["profileUrl"],
                            "count": 0,
                            "titles": set(),  # <-- make sure this exists
                        },
                    )
                    # increment once per publication
                    if lid not in seen_ids_this_pub:
                        entry["count"] += 1
                        seen_ids_this_pub.add(lid)

                    title = (pub.get("title") or "").strip()
                    if title:
                        entry["titles"].add(title)

        if internal_matches:
            pub["internal_coauthors"] = internal_matches

    # ...filter AI pubs, compute skills...
    internal_collaborators = []
    for lid, info in collaborator_counts.items():
        titles_list = sorted(info.get("titles", set()), key=str.casefold)
        internal_collaborators.append({
            "lecturer_id": lid,
            "name": info["name"],
            "profileUrl": info["profileUrl"],
            "count": info["count"],
            "titles": titles_list,
        })
    internal_collaborators.sort(key=lambda x: (-x["count"], x["name"].lower()))


    existing_doc = coll.find_one({"_id": lecturer["_id"]}) or {}
    old_skills = existing_doc.get("ai_skills", [])

    merged_skills  = sorted(set(old_skills) | set(combined_skills))
    is_ai_lecturer = bool(merged_skills)
    
    new_skills = list_delta(merged_skills, old_skills)

    old_interests_txts = normalize_interest_texts(existing_doc.get("scholar_aiinterests", []))
    new_interests_txts = normalize_interest_texts(filtered_interests)
    new_ai_interests   = list_delta(new_interests_txts, old_interests_txts)

    old_pub_titles = extract_pub_titles(existing_doc.get("scholar_aipublications", []))
    new_pub_titles = extract_pub_titles(filtered_publications)
    new_publication_titles = list_delta(new_pub_titles, old_pub_titles)

    old_collab_names = sorted({ (c.get("name") or "").strip()
                                for c in existing_doc.get("internal_collaborators", []) or [] },
                              key=str.casefold)
    new_collab_names = sorted({ (c.get("name") or "").strip()
                                for c in internal_collaborators or [] },
                              key=str.casefold)
    new_internal_collaborators = list_delta(new_collab_names, old_collab_names)

    scholar_scraped_at = iso_now()


    update_fields = {
        "scholar_profile": scholar_profile_url,
        "scholar_aiinterests": filtered_interests,
        "scholar_aipublications": filtered_publications,
        "ai_skills": merged_skills,
        "is_ai_lecturer": is_ai_lecturer,
        "scholar_processed": True,
        "internal_collaborators": internal_collaborators,
        "scholar_scraped_at": scholar_scraped_at,
    }

    # Record the delta if anything changed
    if delta_collector is not None and (new_skills or new_ai_interests or new_publication_titles or new_internal_collaborators):
        delta_collector.append({
            "name":       lecturer.get("name"),
            "school":     lecturer.get("school"),
            "profileUrl": lecturer.get("profileUrl"),
            "source":     "scholar",
            "new_ai_skills": new_skills,
            "new_expertise": [],
            "new_ai_interests": new_ai_interests,
            "new_publication_titles": new_publication_titles,
            "new_internal_collaborators": new_internal_collaborators,
            "scraped_at": scholar_scraped_at,
        })

    coll.update_one({"_id": lecturer["_id"]}, {"$set": update_fields})
    
    print(
        f"Updated {name} with {len(publications)} total publications, "
        f"{len(filtered_interests)} AI interests, and "
        f"{len(filtered_publications)} AI-related publication entries."
    )

def run_scholar_scraper(chosen_school=None, force_update: bool=False, stop_event=None):
    """
    Scrape Scholar for every lecturer in *chosen_school* (or prompt the user
    to pick one).
    Skips names already processed or too ambiguous.
    """
    deltas = []
    report_path = ""
    # If user didn't provide the school, prompt them (unchanged)
    if not chosen_school:
        school_names = sorted(SCHOOL_DATA.keys())
        print("Which School do you want to process for Google Scholar?")
        for i, s in enumerate(school_names, start=1):
            print(f"{i}. {s}")

        choice_str = input("\nEnter a number: ").strip()
        if not choice_str.isdigit():
            print("Invalid choice. Exiting.")
            return
        choice = int(choice_str)
        if choice < 1 or choice > len(school_names):
            print("Invalid choice. Exiting.")
            return

        chosen_school = school_names[choice - 1]

    print(f"\nScraping Google Scholar for lecturers in: {chosen_school}")

    # >>> Filter by the chosen school <<<
    coll = get_lecturers_collection()

    # pull them into a list to avoid cursor timeouts
    matching_lecturers = list(coll.find({"school": chosen_school}))

    count = 0
    try:
        for lecturer_record in matching_lecturers:
            if stop_event and stop_event.is_set():
                print("Cancellation requested; stopping Scholar scraping.")
                break
            raw_name = lecturer_record.get("name", "")
            name = lecturer_record.get("name", "")
            cleaned  = clean_full_name(raw_name)
            if len(cleaned.split()) == 1:
                print(
                    f"Skipping '{lecturer_record.get('name')}'  – single‑word name, profile too ambiguous."
                )
                continue
            # Skips if this profile has previously been scraper and no update requested
            if not force_update and lecturer_record.get("scholar_processed"):
                print(f"Already scraped Scholar for {name}; skipping.")
                continue

            try:
                process_lecturer_record(lecturer_record, deltas)
                time.sleep(random.uniform(5, 10))
                count += 1
            except Exception as ex:
                print(f"Error processing lecturer {lecturer_record.get('name')}: {ex}")
    finally:
            
        report_path = write_delta_report(deltas, source="scholar", school=chosen_school)
        print(f"\nDelta report written to: {report_path}")
        print(f"\nFinished Google Scholar scraping for {count} lecturers in '{chosen_school}'.")
        
    return report_path


if __name__ == "__main__":
    run_scholar_scraper()
