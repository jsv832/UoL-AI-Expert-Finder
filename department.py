"""
department.py
This module has a dictionary containing all the schools of faculties in the University of Leeds
This is used to all the user to scrape for the Lecturers in a specific school
"""

SCHOOL_DATA = {
    # Faculty of Arts, Humanities and Cultures
    "IDEA: The Ethics Centre": {
        "faculty": "Faculty of Arts, Humanities and Cultures",
        "url": "https://ahc.leeds.ac.uk/ethics/stafflist"
    },
    "Institute for Medieval Studies": {
        "faculty": "Faculty of Arts, Humanities and Cultures",
        "url": "https://ahc.leeds.ac.uk/medieval/stafflist"
    },
    "School of Design": {
        "faculty": "Faculty of Arts, Humanities and Cultures",
        "url": "https://ahc.leeds.ac.uk/design/stafflist"
    },
    "School of English": {
        "faculty": "Faculty of Arts, Humanities and Cultures",
        "url": "https://ahc.leeds.ac.uk/english/stafflist"
    },
    "School of Fine Art, History of Art and Cultural Studies": {
        "faculty": "Faculty of Arts, Humanities and Cultures",
        "url": "https://ahc.leeds.ac.uk/fine-art/stafflist"
    },
    "School of History": {
        "faculty": "Faculty of Arts, Humanities and Cultures",
        "url": "https://ahc.leeds.ac.uk/history/stafflist"
    },
    "School of Languages, Cultures and Societies": {
        "faculty": "Faculty of Arts, Humanities and Cultures",
        "url": "https://ahc.leeds.ac.uk/languages/stafflist"
    },
    "Language Centre": {
        "faculty": "Faculty of Arts, Humanities and Cultures",
        "url": "https://ahc.leeds.ac.uk/language-centre/stafflist"
    },
    "School of Media and Communication": {
        "faculty": "Faculty of Arts, Humanities and Cultures",
        "url": "https://ahc.leeds.ac.uk/media/stafflist"
    },
    "School of Music": {
        "faculty": "Faculty of Arts, Humanities and Cultures",
        "url": "https://ahc.leeds.ac.uk/music/stafflist"
    },
    "School of Performance and Cultural Industries": {
        "faculty": "Faculty of Arts, Humanities and Cultures",
        "url": "https://ahc.leeds.ac.uk/performance/stafflist"
    },
    "School of Philosophy, Religion and History of Science": {
        "faculty": "Faculty of Arts, Humanities and Cultures",
        "url": "https://ahc.leeds.ac.uk/philosophy/stafflist"
    },

    # Faculty of Biological Sciences
    "School of Biology": {
        "faculty": "Faculty of Biological Sciences",
        "url": "https://biologicalsciences.leeds.ac.uk/school-of-biology/stafflist"
    },
    "School of Biomedical Sciences": {
        "faculty": "Faculty of Biological Sciences",
        "url": "https://biologicalsciences.leeds.ac.uk/school-biomedical-sciences/stafflist"
    },
    "School of Molecular and Cellular Biology": {
        "faculty": "Faculty of Biological Sciences",
        "url": "https://biologicalsciences.leeds.ac.uk/molecular-and-cellular-biology/stafflist"
    },

    # Faculty of Business
    "Accounting and Finance": {
        "faculty": "Faculty of Business",
        "url": "https://business.leeds.ac.uk/departments-accounting-finance/stafflist"
    },
    "Analytics, Technology and Operations": {
        "faculty": "Faculty of Business",
        "url": "https://business.leeds.ac.uk/departments-analytics-technology-operations/stafflist"
    },
    "Economics": {
        "faculty": "Faculty of Business",
        "url": "https://business.leeds.ac.uk/departments-economics/stafflist"
    },
    "International Business": {
        "faculty": "Faculty of Business",
        "url": "https://business.leeds.ac.uk/departments-international-business/stafflist"
    },
    "Management and Organisations": {
        "faculty": "Faculty of Business",
        "url": "https://business.leeds.ac.uk/departments-management-organisations/stafflist"
    },
    "Marketing": {
        "faculty": "Faculty of Business",
        "url": "https://business.leeds.ac.uk/departments-marketing/stafflist"
    },
    "People, Work and Employment": {
        "faculty": "Faculty of Business",
        "url": "https://business.leeds.ac.uk/departments-people-work-employment/stafflist"
    },

    # Faculty of Engineering and Physical Sciences
    "School of Chemical and Process Engineering": {
        "faculty": "Faculty of Engineering and Physical Sciences",
        "url": "https://eps.leeds.ac.uk/chemical-engineering/stafflist"
    },
    "School of Chemistry": {
        "faculty": "Faculty of Engineering and Physical Sciences",
        "url": "https://eps.leeds.ac.uk/chemistry/stafflist"
    },
    "School of Civil Engineering": {
        "faculty": "Faculty of Engineering and Physical Sciences",
        "url": "https://eps.leeds.ac.uk/civil-engineering/stafflist"
    },
    "School of Computer Science": {
        "faculty": "Faculty of Engineering and Physical Sciences",
        "url": "https://eps.leeds.ac.uk/computing/stafflist"
    },
    "School of Electronic and Electrical Engineering": {
        "faculty": "Faculty of Engineering and Physical Sciences",
        "url": "https://eps.leeds.ac.uk/electronic-engineering/stafflist"
    },
    "School of Mathematics": {
        "faculty": "Faculty of Engineering and Physical Sciences",
        "url": "https://eps.leeds.ac.uk/maths/stafflist"
    },
    "School of Mechanical Engineering": {
        "faculty": "Faculty of Engineering and Physical Sciences",
        "url": "https://eps.leeds.ac.uk/mechanical-engineering/stafflist"
    },
    "School of Physics and Astronomy": {
        "faculty": "Faculty of Engineering and Physical Sciences",
        "url": "https://eps.leeds.ac.uk/physics/stafflist"
    },

    # Faculty of Environment
    "Institute for Transport Studies": {
        "faculty": "Faculty of Environment",
        "url": "https://environment.leeds.ac.uk/transport/stafflist"
    },
    "School of Earth and Environment": {
        "faculty": "Faculty of Environment",
        "url": "https://environment.leeds.ac.uk/see/stafflist"
    },
    "School of Food Science and Nutrition": {
        "faculty": "Faculty of Environment",
        "url": "https://environment.leeds.ac.uk/food-nutrition/stafflist"
    },
    "School of Geography": {
        "faculty": "Faculty of Environment",
        "url": "https://environment.leeds.ac.uk/geography/stafflist"
    },
    "Faculty of Environment": {
        "faculty": "Faculty of Environment",
        "url": "https://environment.leeds.ac.uk/faculty/stafflist"
    },

    # Faculty of Medicine and Health
    "School of Dentistry": {
        "faculty": "Faculty of Medicine and Health",
        "url": "https://medicinehealth.leeds.ac.uk/dentistry/stafflist"
    },
    "School of Healthcare": {
        "faculty": "Faculty of Medicine and Health",
        "url": "https://medicinehealth.leeds.ac.uk/healthcare/stafflist"
    },
    "School of Medicine": {
        "faculty": "Faculty of Medicine and Health",
        "url": "https://medicinehealth.leeds.ac.uk/medicine/stafflist"
    },
    "School of Psychology": {
        "faculty": "Faculty of Medicine and Health",
        "url": "https://medicinehealth.leeds.ac.uk/psychology/stafflist"
    },

    # Faculty of Social Sciences
    "School of Education": {
        "faculty": "Faculty of Social Sciences",
        "url": "https://essl.leeds.ac.uk/education/stafflist"
    },
    "School of Law": {
        "faculty": "Faculty of Social Sciences",
        "url": "https://essl.leeds.ac.uk/law/stafflist"
    },
    "School of Politics and International Studies": {
        "faculty": "Faculty of Social Sciences",
        "url": "https://essl.leeds.ac.uk/politics/stafflist"
    },
    "School of Sociology and Social Policy": {
        "faculty": "Faculty of Social Sciences",
        "url": "https://essl.leeds.ac.uk/sociology/stafflist"
    },
}
