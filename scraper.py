"""
scraper.py
This module scrapes all the Leeds lecturers in a particular School
It will look for AI skills, works or interests for the lecturer and save it on database
Information such as URL, Position, Name are stored to facilitate Google Scholar Scrapping 
"""

import re
import time
import random
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from ai_classifiers import (AI_RELATED_THRESHOLD, combine_all_ai_skills,
                            filter_ai_interests, filter_ai_paragraphs)
from database import get_lecturers_collection
from utils import select_proxy_and_headers
from department import SCHOOL_DATA
from delta import write_delta_report, list_delta, iso_now, safe_slug, merge_csv_reports

#Leeds University Search

def find_staff_profile_links(soup: BeautifulSoup, page_url: str) -> set:
    """
    Finds potential staff profile links on a given staff list page (soup),
    specifically targeting the structure observed on eps.leeds.ac.uk/computing/stafflist.
    Converts relative URLs to absolute URLs based on page_url just in case.
    Returns a set of absolute URLs.
    """
    links = set()
    # Selects the <a> tag within the <td class="title"> in the main profile table
    profile_link_selector = "table.table-profiles tbody tr td.title a"

    found_links = soup.select(profile_link_selector)

    for link_tag in found_links:
        if link_tag.has_attr('href'):
            href = link_tag['href'].strip()
            # Although links look absolute, use urljoin for robustness
            absolute_link = urljoin(page_url, href)

            # Basic filtering: Ensure it's HTTP/HTTPS
            if absolute_link.startswith(("http://", "https://")):
                 # Optional: Add more filtering if needed, e.g., ensure '/staff/' is in the path
                 # if '/staff/' in absolute_link or '/people/' in absolute_link:
                 links.add(absolute_link)

    # Filter out the main staff list page URL itself if it somehow gets included
    if page_url in links:
        links.remove(page_url)
        
    # Also filter out variants that might just be pagination links of the index
    if page_url.split('?')[0] in [l.split('?')[0] for l in links]:
        links = {l for l in links if l.split('?')[0] != page_url.split('?')[0]}


    return links

def find_next_page_url(soup: BeautifulSoup, page_url: str) -> str | None:
    """
    Finds the URL for the next page in a paginated list using selectors
    refined based on eps.leeds.ac.uk/computing/stafflist HTML.
    Returns the absolute URL or None.
    """
    next_url = None

    # REFINED SELECTORS
    # Method 1: Preferred - Look for <link rel="next"> in <head>
    next_link_tag = soup.find('link', rel='next')
    if next_link_tag and next_link_tag.has_attr('href'):
        href = next_link_tag['href'].strip()
        if href and href != '#':
             next_url = urljoin(page_url, href)
             print(f"    Found next page via <link rel='next': {next_url}") 
             # Check if it points back to the same page (unlikely for rel=next but safety)
             if next_url == page_url:
                 next_url = None


    # Method 2: Fallback - Look for <a aria-label="Next"> in pagination block
    if not next_url:
        pagination_next_tag = soup.select_one('ul.pagination li a[aria-label="Next"]')
        if pagination_next_tag and pagination_next_tag.has_attr('href'):
            href = pagination_next_tag['href'].strip()
            if href and href != '#':
                 next_url = urljoin(page_url, href)
                 print(f" Found next page via aria-label='Next': {next_url}") 
                 # Check if it points back to the same page
                 if next_url == page_url:
                      next_url = None


    # Method 3: Alternative Fallback (Less specific, use if above fail)
    # Looks for the link in the list item immediately after the one marked 'active'
    if not next_url:
        active_li = soup.select_one("ul.pagination li.active")
        if active_li:
            next_li = active_li.find_next_sibling("li")
            if next_li:
                next_link_in_li = next_li.find("a")
                if next_link_in_li and next_link_in_li.has_attr("href"):
                    href = next_link_in_li['href'].strip()
                    if href and href != '#':
                        next_url = urljoin(page_url, href)
                        print(f"    Found next page via sibling of active: {next_url}")
                        if next_url == page_url:
                            next_url = None

    # Final check to prevent loops if somehow the next URL is identical
    if next_url == page_url:
        print(f" Warning: Detected next page URL identical to current page ({page_url}). Stopping pagination.")
        return None

    return next_url

def scrape_lecturer_page(url, faculty, school):
    """
    Scrape the lecturer page at 'url'.
    Return a dict with the lecturer's info (including AI analysis),
    and store 'faculty' as 'department', plus 'school'.
    """
    if not url or not url.startswith(("http://", "https://")):
        print(f"Skipping invalid URL: {url!r}")
        return None

    print(f"Scraping: {url}")
    lecturer = {
        "profileUrl": url,
        "name": None,
        "position": None,
        "department": faculty,
        "university": "University of Leeds",
        "school": school,
        "skills_expertise": [],
        "projects": [],
        "current_leeds_lecturer": True,
        "scholar_profile": "",
    }

    headers, proxy = select_proxy_and_headers()
    resp = requests.get(url, headers=headers, proxies=proxy, timeout=30)
    if not resp.ok:
        print(f"Failed to fetch {url}, status={resp.status_code}")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    # Extract Lecturer Name
    name_tag = soup.find("h1", class_="heading-underline")
    if name_tag:
        lecturer["name"] = name_tag.get_text(strip=True)

    # Extract Position and Areas of Expertise and scholar link
    facts_ul = soup.find("ul", class_="list-facts")
    if facts_ul:
        for li in facts_ul.find_all("li"):
            txt = li.get_text(strip=True)

            if txt.lower().startswith("position:"):
                lecturer["position"] = txt.split(":", 1)[1].strip()

            elif txt.lower().startswith("areas of expertise:"):
                exp_str = txt.split(":", 1)[1]
                lecturer["skills_expertise"] = [
                    s.strip() for s in re.split(r"[;,]", exp_str) if s.strip()
                ]

            elif txt.lower().startswith("website"):
                for a in li.find_all("a", href=True):
                    href = a["href"].strip()
                    if "scholar.google" in href:
                        lecturer["scholar_profile"] = href
                        break

    # Grab all paragraphs from the main content to check for AI references
    ai_paragraphs = []
    cms_div = soup.find("div", class_="cms")
    if cms_div:
        paragraph_texts = [p.get_text(strip=True) for p in cms_div.find_all("p")]
        # Filter AI paragraphs from the text
        ai_paragraphs = filter_ai_paragraphs(paragraph_texts, threshold=AI_RELATED_THRESHOLD)


    # 1) AI-related subset of 'skills_expertise'
    ai_interests = filter_ai_interests(lecturer["skills_expertise"], threshold=0.75)

    # 3) Combine skill phrases from interests, publications, and paragraphs
    combined_skills = combine_all_ai_skills(ai_interests,None, ai_paragraphs)
    is_ai_lecturer = bool(combined_skills)

    # Store them in the lecturer data so we can upsert to DB
    lecturer["ai_interests"] = ai_interests
    lecturer["ai_paragraphs"] = ai_paragraphs
    lecturer["ai_skills"] = combined_skills
    lecturer["is_ai_lecturer"] = is_ai_lecturer

    return lecturer

def store_lecturer_in_db(lecturer_data):
    """
    Upsert the lecturer document into MongoDB.
    The 'url' field is used as the unique _id.
    """
    coll = get_lecturers_collection()
    profile_url  = lecturer_data["profileUrl"]
    result = coll.update_one(
        {"profileUrl": profile_url}, 
        {"$set": lecturer_data},
        upsert=True,
    )    
    if result.upserted_id:
        print(f"Inserted new lecturer doc with _id = {result.upserted_id}")
    else:
        print(f"Updated existing lecturer doc with _id = {profile_url}")

def run_leeds_scraper(chosen_school=None, force_update: bool=False, stop_event=None):
    """
    Scrapes staff pages for a chosen school by navigating the staff list
    directly and handling pagination. Stores lecturer info in the database.
    """
    # 1) If no chosen_school was passed, ask the user (same as before)
    deltas = []
    report_path = ""
    if not chosen_school:
        school_names = sorted(SCHOOL_DATA.keys())
        print("Which School do you want to scrape?")
        for i, s in enumerate(school_names, start=1):
            print(f"{i}. {s}")

        choice = input("\nEnter a number: ").strip()
        if not choice.isdigit():
            print("Invalid choice. Exiting.")
            return

        choice_idx = int(choice) - 1
        if choice_idx < 0 or choice_idx >= len(school_names):
            print("Invalid choice. Exiting.")
            return

        chosen_school = school_names[choice_idx]

    # 2) Now chosen_school definitely has a value
    print(f"\nScraping staff pages for School: {chosen_school}")
    if chosen_school not in SCHOOL_DATA:
        print(f"Error: School '{chosen_school}' not found in SCHOOL_DATA.")
        return

    faculty = SCHOOL_DATA[chosen_school]["faculty"]
    staff_url = SCHOOL_DATA[chosen_school]["url"]
    coll = get_lecturers_collection()

    # Scrape index pages
    all_profile_urls = set()
    processed_index_pages = set()
    current_page_url = staff_url
    page_count = 0
    try:
        print("Discovering staff profile URLs...")
        while current_page_url and current_page_url not in processed_index_pages:
            if stop_event and stop_event.is_set():
                print("Cancellation requested; stopping index discovery.")
                break
            page_count += 1
            print(f"  Fetching index page {page_count}: {current_page_url}")
            processed_index_pages.add(current_page_url)

            try:
                headers, proxy = select_proxy_and_headers()
                # Politeness delay before hitting index page
                time.sleep(random.uniform(2, 5)) 
                resp = requests.get(current_page_url, headers=headers, proxies=proxy, timeout=30)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "html.parser")

                # Find profile links on this page
                links_on_page = find_staff_profile_links(soup, current_page_url)
                new_links = links_on_page - all_profile_urls
                if new_links:
                    print(f"Found {len(new_links)} new profile URLs.")
                    all_profile_urls.update(new_links)
                else:
                    print("No new profile URLs found on this page.")


                # Find the next page URL
                current_page_url = find_next_page_url(soup, current_page_url)
                if current_page_url:
                    print(f"Found next page link: {current_page_url}")
                else:
                    print("No next page link found.")


            except requests.exceptions.RequestException as e:
                print(f"Error fetching index page {current_page_url}: {e}")
                current_page_url = None 
            except Exception as e:
                print(f"Error processing index page {current_page_url}: {e}")
                current_page_url = None 

        print(f"\nFinished discovering URLs. Total unique profile URLs found: {len(all_profile_urls)}")
        if not all_profile_urls:
            print("No profile URLs found. Check selectors in find_staff_profile_links or the staff URL.")
            return

        # Process discovered profile URLs
        processed_count = 0
        skipped_count = 0
        error_count = 0
        total_to_process = len(all_profile_urls)

        print(f"\nStarting to scrape {total_to_process} individual profiles...")

        for i, url in enumerate(all_profile_urls, 1):
            if stop_event and stop_event.is_set():
                print("Cancellation requested; stopping profile scraping.")
                break
            print(f"\n--- Processing profile {i}/{total_to_process} ---")
            # Skip if already scraped and no update requested
            # Check using exists() might be slightly faster if the document is large
            if not force_update and coll.count_documents({"profileUrl": url}, limit = 1) > 0:
                print(f"Already scraped (and force_update=False): {url}")
                skipped_count += 1
                continue

            # Otherwise, scrape and store
            # Politeness delay before hitting profile page
            time.sleep(random.uniform(1, 3)) 
            lecturer_data = scrape_lecturer_page(url, faculty, chosen_school)

            if lecturer_data:
                # Compare against existing to compute delta
                existing_doc = coll.find_one({"profileUrl": url}) or {}
                old_skills     = existing_doc.get("ai_skills", []) or []
                old_expertise  = existing_doc.get("skills_expertise", []) or []

                new_skills     = list_delta(lecturer_data.get("ai_skills", []), old_skills)
                new_expertise  = list_delta(lecturer_data.get("skills_expertise", []), old_expertise)

                # stamp scrape time for Leeds
                lecturer_data["leeds_scraped_at"] = iso_now()

                # only record a delta row if there were changes
                if new_skills or new_expertise:
                    deltas.append({
                        "name":        lecturer_data.get("name") or existing_doc.get("name"),
                        "school":      lecturer_data.get("school") or existing_doc.get("school"),
                        "profileUrl":  url,
                        "source":      "leeds",
                        "new_ai_skills": new_skills,
                        "new_expertise": new_expertise,
                        "new_ai_interests": [],
                        "new_publication_titles": [],
                        "new_internal_collaborators": [],
                        "scraped_at":  lecturer_data["leeds_scraped_at"],
                    })
                store_lecturer_in_db(lecturer_data)
                processed_count += 1
            else:
                # scrape_lecturer_page returns None on error or if name couldn't be found
                print(f"Skipped storing due to error or missing name: {url}")
                error_count += 1
    finally:        
        report_path = write_delta_report(deltas, source="leeds", school=chosen_school)
        print(f"\nDelta report written to: {report_path}")
            
    print("\n--- Scraping Summary ---")
    print(f"School: {chosen_school}")
    print(f"Total unique profile URLs found: {total_to_process}")
    print(f"Successfully processed/stored: {processed_count}")
    print(f"Skipped (already existed, no force_update): {skipped_count}")
    print(f"Skipped (error or missing name during scrape): {error_count}")
    print("------------------------")
    
    return report_path


if __name__ == "__main__":
    # Example of how to run it directly (add argument parsing for school/force if needed)
    # run_leeds_scraper(chosen_school="School of Computer Science", force_update=False)
    run_leeds_scraper()