"""
main.py
This module allows the user to run both the Scraper through the Terminal
"""
import sys
from database import get_lecturers_collection
from scholar_scraper import run_scholar_scraper
from scraper import run_leeds_scraper
from department import SCHOOL_DATA

def ask_force_update() -> bool:
    while True:
        ans = input("Update existing entries as well? [Y/N]: ").strip()
        if ans.upper().startswith("Y"):
            return True
        if ans.upper().startswith("N") or ans == "":
            return False
        print("Please answer with Y or N.")


def main():
    while True:                                          

        print("Choose an option:")
        print("1. Scrape University of Leeds lecturers")
        print("2. Scrape Google Scholar profiles")
        print("3. Run both sequentially (same School)")
        print("9. Exit")

        choice = input("Enter your choice (1/2/3): ").strip()
        # Choice results
        if choice == "9":
            print("Good-bye!")
            sys.exit(0)

        if choice == "1":
            force_upd = ask_force_update() 
            print("\nRunning University of Leeds lecturers scraper...")
            run_leeds_scraper(force_update=force_upd)
            sys.exit(0) 
                            
        elif choice == "2":
            force_upd = ask_force_update() 
            print("\nRunning Google Scholar scraper...")
            run_scholar_scraper(force_update=force_upd)
            sys.exit(0) 
                         
        if choice == "3":
            school_names = sorted(SCHOOL_DATA.keys())
            while True:                                  
                print("\nChoose the School (applies to *both* scrapers):")
                for i, s in enumerate(school_names, 1):
                    print(f"{i}. {s}")
                school_opt = input("\nEnter number (or blank to cancel): ").strip()

                if school_opt == "":   
                    break                  

                if school_opt.isdigit() and 1 <= int(school_opt) <= len(school_names):
                    chosen_school = school_names[int(school_opt) - 1]
                    print(f"\nYou selected: {chosen_school}")
                    force_upd = ask_force_update()

                    print("\nRunning University of Leeds lecturers scraper…")
                    run_leeds_scraper(chosen_school=chosen_school,
                                      force_update=force_upd)

                    print("\nRunning Google Scholar scraper…")
                    run_scholar_scraper(chosen_school=chosen_school,
                                        force_update=force_upd)
                    sys.exit(0)  

                print("Please enter a valid number.")
            continue

        print("Please choose 1, 2, 3 or 9.")


if __name__ == "__main__":
    main()
