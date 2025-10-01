"""
interface.py
This module provides an interface where the user has access to all features of the project
Access to Database, Skills, Lecturers Information and Both Scrapers
It also allows for more specialised searches. If user wants to find lecturers with specific skills.
"""
import sys

import pymongo
from PyQt5.QtCore import Qt, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (QAction, QApplication, QCheckBox, QComboBox,
                             QDialog, QFormLayout, QHBoxLayout, QLabel,
                             QLineEdit, QListWidget, QListWidgetItem,
                             QMainWindow, QMessageBox, QPlainTextEdit,
                             QProgressDialog, QPushButton, QScrollArea,
                             QTabWidget, QTreeWidget, QTreeWidgetItem,
                             QVBoxLayout, QWidget,QGridLayout,QGroupBox)
from threading import Event
from database import get_lecturers_collection
from department import SCHOOL_DATA
from scholar_scraper import run_scholar_scraper
from scraper import run_leeds_scraper
from delta import merge_csv_reports
import re
import spacy


# Required for search queries
# Robotics turns into robotic 
nlp = spacy.load("en_core_web_sm", disable=["parser", "ner"])
def plural_fix(term: str) -> str:
    """
    Build a regex that matches both the lemma and every simple
    inflection of that lemma (plurals, -ing, -ed, …).
    Multi-word terms (e.g. 'machine learning') are returned unchanged.
    """
    # multi-word skills → just escape them
    doc = nlp(term.lower().replace("-", " "))   # normalise hyphens → spaces

    pieces: list[str] = []
    for tok in doc:
        lemma = tok.lemma_ or tok.text

        # keep only “real” word tokens: letters or digits
        if not lemma.isalnum():
            continue

        pieces.append(rf"{re.escape(lemma)}\w*")
    # degenerate input like "@@"
    if not pieces:                       
        return re.escape(term)

    # zero-or-MORE hyphens/spaces between pieces:
    separator = r"(?:[-\s]*)"
    return r"\b" + separator.join(pieces) + r"\b"


# Scraper Class
class ScrapeWorker(QThread):
    """
    Runs one or both scrapers in a background thread so the GUI doesn't freeze.
    We'll rely on bool flags to decide which scrapers to run.
    """
    # Emitted when scraping finishes
    done_signal = pyqtSignal()  
    # Emitted when scraping fails
    error_signal = pyqtSignal(str)  

    def __init__(self, leeds_only, scholar_only, force_update=False, 
                chosen_school=None, parent=None):
        super().__init__(parent)
        self.stop_event = Event()
        self.leeds_only = leeds_only
        self.scholar_only = scholar_only
        self.force_update = force_update
        self.chosen_school = chosen_school
        self.err_msg = "" 
        
    def run(self):
        try:
            leeds_path = None
            scholar_path = None

            if self.leeds_only:
                leeds_path = run_leeds_scraper(
                    chosen_school=self.chosen_school,
                    force_update=self.force_update,
                    stop_event=self.stop_event,   # <— new
                )

            if self.scholar_only:
                scholar_path = run_scholar_scraper(
                    chosen_school=self.chosen_school,
                    force_update=self.force_update,
                    stop_event=self.stop_event,   # <— new
                )

            self.report_leeds = leeds_path
            self.report_scholar = scholar_path
            combined = None
            if self.leeds_only and self.scholar_only:
                combined = merge_csv_reports(
                    [p for p in (leeds_path, scholar_path) if p],
                    school=self.chosen_school
                )
            self.last_report_path = combined or leeds_path or scholar_path

        except Exception as exc:
            self.err_msg = str(exc)
            self.error_signal.emit(self.err_msg)
        finally:
            self.done_signal.emit()


#  1)Professor Detail Dialog
class ProfessorDetailDialog(QDialog):
    """
    If 'filtered_skills' is provided, we only display that subset of skills
    instead of all skills from prof_doc["ai_skills"].
    """

    def __init__(self, prof_doc, parent=None, filtered_skills=None):
        super().__init__(parent)
        self.prof_doc = prof_doc
        self.setWindowTitle(f"Professor Details: {prof_doc.get('name', 'Unknown')}")
        self.resize(600, 500)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        container = QWidget()
        form_layout = QFormLayout(container)

        # Extract data
        name = prof_doc.get("name", "Unknown")
        school = prof_doc.get("school", "")
        position = prof_doc.get("position", "")

        # If filtered_skills is not None, we use that subset
        if filtered_skills is not None:
            ai_skills = filtered_skills
        else:
            ai_skills = prof_doc.get("ai_skills", [])

        # Show these fields too
        expertise = prof_doc.get("skills_expertise", [])
        scholar_link = prof_doc.get("scholar_profile", "")
        publications = prof_doc.get("scholar_aipublications") or prof_doc.get("ai_publications", [])
        internal_collabs = prof_doc.get("internal_collaborators", [])
        
        # Also the URL to their Leeds page (if stored)
        leeds_url = prof_doc.get("url", "") 
        # Basic fields
        form_layout.addRow("Name:", QLabel(name))
        if school:
            form_layout.addRow("School:", QLabel(school))
        if position:
            form_layout.addRow("Position:", QLabel(position))

        # AI Skills in a list
        if ai_skills:
            skills_list_widget = QListWidget()
            for skill in ai_skills:
                QListWidgetItem(skill, skills_list_widget)
            form_layout.addRow("AI Skills:", skills_list_widget)

        # Skills of expertise
        if expertise:
            expertise_list = QListWidget()
            for exp in expertise:
                QListWidgetItem(exp, expertise_list)
            form_layout.addRow("Skills of Expertise:", expertise_list)

        # University Leeds page link
        if leeds_url:
            link_label = QLabel(f'<a href="{leeds_url}">Open Leeds Profile Page</a>')
            link_label.setTextFormat(Qt.RichText)
            link_label.setTextInteractionFlags(Qt.TextBrowserInteraction)
            link_label.setOpenExternalLinks(True)
            form_layout.addRow("Leeds URL:", link_label)

        # Scholar link - clickable hyperlink
        if scholar_link:
            scholar_label = QLabel(f'<a href="{scholar_link}">Open Google Scholar Profile</a>')
            scholar_label.setTextFormat(Qt.RichText)
            scholar_label.setTextInteractionFlags(Qt.TextBrowserInteraction)
            scholar_label.setOpenExternalLinks(True)
            form_layout.addRow("Google Scholar:", scholar_label)
        
        #Internal Collaborators (in-database coauthors)
        if internal_collabs:
            collab_tree = QTreeWidget()
            collab_tree.setColumnCount(2)
            collab_tree.setHeaderLabels(["Collaborator", "Coauthored Pubs"])

            # Optional: nicer sizing
            collab_tree.header().setStretchLastSection(False)
            collab_tree.header().setSectionResizeMode(0, collab_tree.header().ResizeToContents)
            collab_tree.header().setSectionResizeMode(1, collab_tree.header().ResizeToContents)

            # If older records have no 'titles', we’ll try to infer them from scholar_publications_all
            fallback_pubs = prof_doc.get("scholar_publications_all", []) or []

            for c in internal_collabs:
                name = c.get("name", "Unknown")
                count = c.get("count", 0)
                titles = c.get("titles")  # may be None for older records

                if titles is None:
                    # Fallback: derive titles by scanning raw pubs for this collaborator id
                    # (Works even if DB hasn’t been re-scraped yet to include 'titles'.)
                    titles = []
                    cid = c.get("lecturer_id")
                    for pub in fallback_pubs:
                        for co in pub.get("internal_coauthors", []) or []:
                            if co.get("lecturer_id") == cid:
                                t = (pub.get("title") or "").strip()
                                if t:
                                    titles.append(t)
                    # dedupe and sort
                    titles = sorted(sorted(set(titles)), key=str.casefold)

                top = QTreeWidgetItem([f"{name}", f"{count}"])
                collab_tree.addTopLevelItem(top)

                for t in titles:
                    QTreeWidgetItem(top, [t, ""])   # child rows show titles

                # expand rows by default if there are few; otherwise leave collapsed
                if len(titles) <= 3:
                    collab_tree.expandItem(top)

            form_layout.addRow("Internal Collaborators:", collab_tree)
            
        # Publications
        if publications:
            pubs_text_lines = []
            for pub in publications:
                title = pub.get("title", "")
                year = pub.get("year", "")
                authors = pub.get("authors", "")
                line = title
                if year:
                    line += f" ({year})"
                if authors:
                    line += f" — {authors}"
                pubs_text_lines.append(line.strip(" —"))
            pubs_big_text = "\n".join(pubs_text_lines)
            pubs_edit = QPlainTextEdit(pubs_big_text)
            pubs_edit.setReadOnly(True)
            form_layout.addRow("AI Publications:", pubs_edit)

        scroll.setWidget(container)
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(scroll)
        self.setLayout(main_layout)


# --------------------------------------------------------------------
# 2) Scraper Tab
# --------------------------------------------------------------------
class RunScrapersTab(QWidget):
    scraped = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)

        # Options group  
        # School selector and force-update checkbox
        options_box = QGroupBox("Scrape options")
        opt_grid = QGridLayout(options_box)
        opt_grid.setColumnStretch(1, 1) 

        # School selector
        lbl_school = QLabel("School:")
        self.school_combo = QComboBox()
        self.school_combo.addItem(" Select a School ")
        for sch in sorted(SCHOOL_DATA.keys()):
            self.school_combo.addItem(sch)

        opt_grid.addWidget(lbl_school,        0, 0, Qt.AlignLeft)
        opt_grid.addWidget(self.school_combo, 0, 1)
        lbl_school.setStyleSheet("font-size: 11pt;")          
        self.school_combo.setMinimumHeight(32)       
        self.school_combo.setStyleSheet("font-size: 11pt;")
        
        # Force-update checkbox
        self.force_update_cb = QCheckBox("Re-scrape lecturers already in DB")
        self.force_update_cb.setToolTip(
            "Tick this if you want to update lecturers that have been scraped before."
        )
        self.force_update_cb.setStyleSheet("""
        QCheckBox::indicator {      /* the tick-box itself */
            width: 20px;
            height: 20px;
        }
        QCheckBox {                 /* the label text */
            font-size: 11pt;
        }
    """)

        opt_grid.addWidget(self.force_update_cb, 1, 0, 1, 2)

        main_layout.addWidget(options_box)


        #Row of scraper buttons
        btn_layout = QHBoxLayout()
        self.btn_leeds   = QPushButton("Run Leeds Scraper")
        self.btn_scholar = QPushButton("Run Scholar Scraper")
        self.btn_both    = QPushButton("Run Both")
        btn_layout.addWidget(self.btn_leeds)
        btn_layout.addWidget(self.btn_scholar)
        btn_layout.addWidget(self.btn_both)
        for b in (self.btn_leeds, self.btn_scholar, self.btn_both):
            b.setMinimumHeight(40)
        main_layout.addLayout(btn_layout)

        # Wire signals 
        self.btn_leeds.clicked.connect(self.run_leeds_scraper_chosen)
        self.btn_scholar.clicked.connect(self.run_scholar_scraper_chosen)
        self.btn_both.clicked.connect(self.run_both_scrapers)

    def get_chosen_school(self):
        """Helper to get the chosen school or None if 'All (Prompt user)'."""
        if self.school_combo.currentIndex() == 0:
            return None
        return self.school_combo.currentText()
    
    def force_update_requested(self) -> bool:
       """Return True if the user ticked the ‘force update’ option."""
       return self.force_update_cb.isChecked()
   
    def run_leeds_scraper_chosen(self):
        chosen_school = self.get_chosen_school()
        if chosen_school is None:
            QMessageBox.warning(
                self, "Choose a School",
                "Please select a specific school before running the Leeds scraper."
            )
            return
        self.start_scrape_thread(
            leeds_only=True, scholar_only=False, chosen_school=chosen_school)

    def run_scholar_scraper_chosen(self):
        chosen_school = self.get_chosen_school()
        if chosen_school is None:
            QMessageBox.warning(
                self, "Choose a School",
                "Please select a specific school before running the Scholar scraper."
            )
            return   
        if chosen_school is not None:
            coll = get_lecturers_collection()
            doc_count = coll.count_documents({"school": chosen_school})
            if doc_count == 0:
                QMessageBox.warning(
                    self,
                    "Not Yet Scraped",
                    f"No lecturers found for '{chosen_school}' in DB.\n"
                    f"Please run the Leeds scraper for that school first!",
                )
                return
        self.start_scrape_thread(leeds_only=False, scholar_only=True, chosen_school=chosen_school)

    def run_both_scrapers(self):
        chosen_school = self.get_chosen_school()
        if chosen_school is None:
            QMessageBox.warning(
                    self, "Choose a School",
                    "Please select a specific school before running both scrapers."
                )
            return
        # Run both in the background
        self.start_scrape_thread(leeds_only=True, scholar_only=True, chosen_school=chosen_school)

    def start_scrape_thread(self, leeds_only, scholar_only, chosen_school):
        """Creates a background worker thread so the GUI won't freeze."""
        # Show a progress dialog
        self.progress_dialog = QProgressDialog("Scraping in progress...", "Cancel", 0, 0, self)
        self.progress_dialog.setWindowTitle("Scraping")
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.show()

        # Create the worker
        self.worker = ScrapeWorker(leeds_only, scholar_only,force_update=self.force_update_requested(), chosen_school=chosen_school)
        # Connect the worker's error signal
        self.worker.error_signal.connect(self.on_scrape_error)
        # Connect the worker's finished signal
        self.worker.done_signal.connect(self.on_scrape_finished)

        # If user presses Cancel, we can attempt to stop the worker
        self.progress_dialog.canceled.connect(self.on_cancel_scrape)

        # Start the worker in a separate thread
        self.worker.start()

    def on_scrape_finished(self):
        """Called when worker is done."""
        if self.progress_dialog:
            self.progress_dialog.reset()
            self.progress_dialog = None
        if getattr(self.worker, "err_msg", ""):
            # Error case already shown via on_scrape_error
            self.scraped.emit()
            return

        msg_lines = ["Scraping is complete!"]
        # Show combined path if present, otherwise show whichever exists
        
        if getattr(self.worker, "last_report_path", ""):
            msg_lines.append(f"Delta report: {self.worker.last_report_path}")
            
        # Also show individual component reports when both were run
        if getattr(self.worker, "report_leeds", "") and getattr(self.worker, "report_scholar", ""):
            msg_lines.append(f"Leeds report: {self.worker.report_leeds}")
            msg_lines.append(f"Scholar report: {self.worker.report_scholar}")

        QMessageBox.information(self, "Done", "\n\n".join(msg_lines))
        self.scraped.emit()

    def on_cancel_scrape(self):
        if self.worker.isRunning():
            self.worker.stop_event.set()                      
            self.progress_dialog.setLabelText("Cancelling…")  
            self.progress_dialog.setCancelButtonText("Close")

    @pyqtSlot(str)
    def on_scrape_error(self, message: str):
        """Called immediately when the worker emits an error."""
        if self.progress_dialog:                     
            self.progress_dialog.reset()
            self.progress_dialog = None
        QMessageBox.critical(self,
                             "Scraping Error",
                             f"An error occurred while scraping:\n\n{message}")

# --------------------------------------------------------------------
# 3) Professor List Tab
# --------------------------------------------------------------------
class ProfessorListTab(QWidget):
    def __init__(self, db_collection, parent=None):
        super().__init__(parent)
        self.collection = db_collection
        layout = QVBoxLayout(self)

        # Filter by School
        self.school_filter = QComboBox()
        layout.addWidget(QLabel("Filter by School:"))
        layout.addWidget(self.school_filter)

        # Filter by partial Name
        self.name_search_input = QLineEdit()
        self.name_search_input.setPlaceholderText("Enter partial professor name...")
        self.btn_name_search = QPushButton("Search Name")
        layout.addWidget(QLabel("Search by Name:"))
        layout.addWidget(self.name_search_input)
        layout.addWidget(self.btn_name_search)

        # NEW: CheckBox for AI Lecturers Only
        self.ai_checkbox = QCheckBox("Show Only AI Lecturers")
        layout.addWidget(self.ai_checkbox)

        # Tree
        self.tree = QTreeWidget()
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels(["Professor Name", "School"])
        layout.addWidget(self.tree)

        self.setLayout(layout)

        # Load data
        self.load_professors()

        # Connect signals
        self.school_filter.currentTextChanged.connect(self.update_filters)
        self.btn_name_search.clicked.connect(self.update_filters)
        self.ai_checkbox.stateChanged.connect(self.update_filters)
        self.tree.itemDoubleClicked.connect(self.show_professor_details)

    @pyqtSlot()
    def load_professors(self):
        self.tree.clear()
        self.school_filter.clear()

        if self.collection is None:
            return

        try:
            professors = list(self.collection.find())
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Failed to load professors:\n{e}")
            return

        schools = sorted({prof.get("school", "Unknown") for prof in professors})
        self.school_filter.addItem("All Schools")
        for sch in schools:
            self.school_filter.addItem(sch)

        for prof in professors:
            self.add_professor_item(prof)

        self.update_filters()

    def add_professor_item(self, prof_doc):
        name = prof_doc.get("name", "Unknown")
        school = prof_doc.get("school", "")
        item = QTreeWidgetItem([name, school])
        item.setData(0, Qt.UserRole, prof_doc)
        self.tree.addTopLevelItem(item)

    def update_filters(self):
        selected_school = self.school_filter.currentText().lower()
        name_search = self.name_search_input.text().strip().lower()
        ai_only = self.ai_checkbox.isChecked()

        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            prof_doc = item.data(0, Qt.UserRole) or {}

            # School filter
            item_school = (prof_doc.get("school") or "").lower()
            hide_by_school = False
            if selected_school not in ("", "all schools"):
                if item_school != selected_school:
                    hide_by_school = True

            # Name filter
            prof_name = (prof_doc.get("name") or "").lower()
            hide_by_name = False
            if name_search and name_search not in prof_name:
                hide_by_name = True

            # NEW: AI-only filter
            is_ai = prof_doc.get("is_ai_lecturer", False)
            hide_by_ai = False
            if ai_only and not is_ai:
                hide_by_ai = True

            # Hide if any filter says so
            item.setHidden(hide_by_school or hide_by_name or hide_by_ai)

    def show_professor_details(self, item, column):
        prof_doc = item.data(0, Qt.UserRole)
        if not prof_doc:
            return

        all_skills = prof_doc.get("ai_skills", [])

        dlg = ProfessorDetailDialog(prof_doc, parent=self, filtered_skills=all_skills)
        dlg.exec_()



# --------------------------------------------------------------------
# 4) Skill Search Tab
# --------------------------------------------------------------------
class SkillSearchTab(QWidget):
    def __init__(self, db_collection, parent=None):
        super().__init__(parent)
        self.collection = db_collection

        main_layout = QVBoxLayout(self)

        # Top row: School filter + Logic selection
        self.school_filter = QComboBox()
        self.school_filter.addItem("All Schools")
        if self.collection is not None:
            try:
                schools = sorted(self.collection.distinct("school"))
                for sch in schools:
                    if sch:
                        self.school_filter.addItem(sch)
            except Exception as e:
                QMessageBox.warning(self, "Database Warning", f"Could not load schools:\n{e}")

        self.logic_combo = QComboBox()
        self.logic_combo.addItems(["AND", "OR"])

        top_row_layout = QHBoxLayout()
        top_row_layout.addWidget(QLabel("School:"))
        top_row_layout.addWidget(self.school_filter)
        top_row_layout.addWidget(QLabel("Logic:"))
        top_row_layout.addWidget(self.logic_combo)
        main_layout.addLayout(top_row_layout)

        # Middle row: Add skill
        add_skill_layout = QHBoxLayout()
        self.new_skill_input = QLineEdit()
        self.new_skill_input.setPlaceholderText("Enter one skill...")
        self.btn_add_skill = QPushButton("Add Skill")
        self.btn_remove_skill = QPushButton("Remove Selected Skill(s)")

        add_skill_layout.addWidget(QLabel("Add AI Skill Filter:"))
        add_skill_layout.addWidget(self.new_skill_input)
        add_skill_layout.addWidget(self.btn_add_skill)
        add_skill_layout.addWidget(self.btn_remove_skill)
        main_layout.addLayout(add_skill_layout)

        # Active skills list
        self.active_skills_list = QListWidget()
        self.active_skills_list.setSelectionMode(QListWidget.ExtendedSelection)
        main_layout.addWidget(QLabel("Current Skill Filters:"))
        main_layout.addWidget(self.active_skills_list)

        # Search button
        self.btn_search = QPushButton("Search")
        main_layout.addWidget(self.btn_search)

        # Results tree
        self.tree = QTreeWidget()
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels(["Professor Name", "School"])
        main_layout.addWidget(QLabel("Results:"))
        main_layout.addWidget(self.tree)

        self.setLayout(main_layout)

        # Connections
        self.btn_add_skill.clicked.connect(self.add_skill_filter)
        self.btn_remove_skill.clicked.connect(self.remove_selected_skills)
        self.btn_search.clicked.connect(self.perform_search)
        self.tree.itemDoubleClicked.connect(self.show_professor_details)

        self.last_skill_terms = []
        self.last_logic = "AND"

    @pyqtSlot()
    def load_professors(self):
        # rebuild the school combo --------------------------
        self.school_filter.blockSignals(True)
        self.school_filter.clear()
        self.school_filter.addItem("All Schools")
        if self.collection is not None:
            for sch in sorted(self.collection.distinct("school")):
                if sch:
                    self.school_filter.addItem(sch)
        self.school_filter.blockSignals(False)

        # if the user already entered some skills, re‑run the search
        if self.last_skill_terms:
            self.perform_search()

    def add_skill_filter(self):
        new_skill = self.new_skill_input.text().strip()
        if new_skill:
            existing = [
                self.active_skills_list.item(i).text()
                for i in range(self.active_skills_list.count())
            ]
            if new_skill not in existing:
                QListWidgetItem(new_skill, self.active_skills_list)
        self.new_skill_input.clear()
        self.new_skill_input.setFocus()

    def remove_selected_skills(self):
        for item in self.active_skills_list.selectedItems():
            self.active_skills_list.takeItem(self.active_skills_list.row(item))

    def perform_search(self):
        self.tree.clear()
        if self.collection is None:
            return

        skill_terms = []
        for i in range(self.active_skills_list.count()):
            skill_terms.append(self.active_skills_list.item(i).text())

        selected_school = self.school_filter.currentText()
        self.last_skill_terms = skill_terms
        self.last_logic = self.logic_combo.currentText()

        if not skill_terms:
            QMessageBox.information(self, "No Skills", "Please add at least one skill to filter.")
            return

        sub_queries = []
        for term in skill_terms:
            pattern = plural_fix(term)
            sub_queries.append({
                "$or": [
                    {"ai_skills":              {"$regex": pattern, "$options": "i"}},
                    {"ai_publications.title":  {"$regex": pattern, "$options": "i"}},
                    {"skills_expertise":       {"$regex": pattern, "$options": "i"}}
                ]
            })

        if self.last_logic == "AND":
            query_filter = {"$and": sub_queries}
        else:
            query_filter = {"$or": sub_queries}

        if selected_school and selected_school != "All Schools":
            if self.last_logic == "AND":
                query_filter["$and"].append({"school": selected_school})
            else:
                query_filter = {"$and": [query_filter, {"school": selected_school}]}

        try:
            matches = list(self.collection.find(query_filter))
        except Exception as e:
            QMessageBox.critical(self, "Search Error", f"Failed to perform search:\n{e}")
            return

        if not matches:
            QMessageBox.information(
                self, "No Results", "No professors found matching those skill(s)."
            )
            return

        for prof in matches:
            self.add_result_item(prof)

    def add_result_item(self, prof_doc):
        name = prof_doc.get("name", "Unknown")
        school = prof_doc.get("school", "")
        item = QTreeWidgetItem([name, school])
        item.setData(0, Qt.UserRole, prof_doc)
        self.tree.addTopLevelItem(item)

    def show_professor_details(self, item, column):
        prof_doc = item.data(0, Qt.UserRole)
        if not prof_doc:
            return

        ai_skills = prof_doc.get("ai_skills", [])
        search_terms = [t.lower() for t in self.last_skill_terms]

        # -------------------- NEW LOGIC --------------------
        # Keep an AI-skill if it contains *any* of the terms,
        # regardless of whether the global search was AND or OR
        matched_skills = [
            s for s in ai_skills
            if any(term in s.lower() for term in search_terms)
        ]

        # If no AI-skill matched, show the complete list instead,
        # so the dialog is never empty.
        filtered = matched_skills or None
        # ---------------------------------------------------

        dlg = ProfessorDetailDialog(prof_doc, parent=self, filtered_skills=filtered)
        dlg.exec_()


# --------------------------------------------------------------------
# 5) Main Application Window
# --------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Leeds AI Researcher Tool")
        self.resize(1200, 700)

        try:
            #Database commented out for privacy reasons

            client = pymongo.MongoClient(
                ""
            )
            db = client["projectdb"]
            lecturers_coll = db["lecturers"]
        except Exception as e:
            QMessageBox.critical(self, "Startup Error", f"Failed to connect to database:\n{e}")
            lecturers_coll = None

        tabs = QTabWidget()
        # style the tabs to be larger
        tabs.setStyleSheet(
            """
            QTabBar::tab {
                height: 18px;
                padding: 6px 12px;
                font-size: 10pt;
            }
            QTabBar::tab:selected {
                background: #e2e2e2;
            }
        """
        )
        self.setCentralWidget(tabs)

        self.run_tab = RunScrapersTab()
        self.prof_list_tab = ProfessorListTab(lecturers_coll)
        self.search_tab = SkillSearchTab(lecturers_coll)

        tabs.addTab(self.run_tab, "Run Scrapers")
        tabs.addTab(self.prof_list_tab, "Professor List")
        tabs.addTab(self.search_tab, "Skill Search")

        # Update them if scraper is ran
        self.run_tab.scraped.connect(self.prof_list_tab.load_professors)
        self.run_tab.scraped.connect(self.search_tab.load_professors)

        # Create a toolbar action
        reload_act = QAction("Reload Data", self)
        reload_act.setShortcut("F5")
        reload_act.setStatusTip("Reload professors & skills from database")

        # Connect it to both tabs
        reload_act.triggered.connect(self.prof_list_tab.load_professors)
        reload_act.triggered.connect(self.search_tab.load_professors)

        # Add it to a toolbar
        toolbar = self.addToolBar("Main")
        toolbar.addAction(reload_act)


# --------------------------------------------------------------------
# 6) Run the application
# --------------------------------------------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    # make everything bigger by default
    app.setFont(QFont("Segoe UI", 10))
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())
