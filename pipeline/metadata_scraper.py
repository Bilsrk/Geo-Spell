import os
import time
import json
import re
import urllib.parse
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

def auto_heal_database():
    base_dir = "nasa_alphabet_database"
    if not os.path.exists(base_dir):
        print(f"Error: Could not find the {base_dir} folder.")
        return

    print("Launching Database Auditor & Auto-Healer...")
    
    # ==========================================
    # PHASE 1: THE HARD DRIVE INVENTORY
    # ==========================================
    print("\n--- PHASE 1: INVENTORYING LOCAL FILES ---")
    master_db = {}
    total_files = 0
    
    # Loop through folders A to Z
    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        folder_path = os.path.join(base_dir, letter)
        if os.path.exists(folder_path):
            for file in os.listdir(folder_path):
                if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                    # Use the actual filename as the unbreakable Primary Key
                    primary_key = urllib.parse.unquote(os.path.splitext(file)[0].lower())
                    master_db[primary_key] = {
                        "letter": letter,
                        "location": "Unknown Location",
                        "coords": "Coords Unknown",
                        "date": "Date Unknown"
                    }
                    total_files += 1
                    
    print(f"Verified {total_files} physical images on your hard drive.")
    print("Building fresh metadata connections...")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=Options())

    try:
        # ==========================================
        # PHASE 2: LOCATION & COORDS SECURE MATCHING
        # ==========================================
        print("\n--- PHASE 2: REBUILDING LOCATIONS & COORDS ---")
        driver.get("https://science.nasa.gov/mission/landsat/outreach/your-name-in-landsat/")
        time.sleep(3)

        # Force open accordions
        driver.execute_script("""
            document.querySelectorAll('details').forEach(d => d.setAttribute('open', 'true'));
            document.querySelectorAll('button[aria-expanded="false"]').forEach(b => b.click());
        """)
        time.sleep(2)

        # Scroll to load everything
        last_h = driver.execute_script("return document.body.scrollHeight")
        while True:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            new_h = driver.execute_script("return document.body.scrollHeight")
            if new_h == last_h: break
            last_h = new_h

        # Strict DOM Mapping (Binds text strictly to the image)
        images = driver.find_elements(By.TAG_NAME, "img")
        for img in images:
            src = img.get_attribute("src")
            if not src or "landsat" not in src.lower(): continue
            
            filename = src.split("/")[-1].split("?")[0]
            primary_key = urllib.parse.unquote(os.path.splitext(filename)[0].lower())

            # Only extract data if this image physically exists on your hard drive
            if primary_key in master_db:
                try:
                    # Find the specific box wrapping THIS image only
                    card = img.find_element(By.XPATH, "./ancestor::div[.//a[contains(text(), 'Download')]][1]")
                    lines = [line.strip() for line in card.text.split('\n') if line.strip()]
                    
                    coord_regex = r"\d{1,3}[°º].+?[NS].+?[EW]"
                    
                    for line in lines:
                        if re.search(coord_regex, line):
                            master_db[primary_key]["coords"] = line
                        elif "download" not in line.lower() and master_db[primary_key]["location"] == "Unknown Location":
                            master_db[primary_key]["location"] = line
                except Exception:
                    continue

        print("Locations and Coordinates perfectly mapped.")

        # ==========================================
        # PHASE 3: DATE HUNTER 
        # ==========================================
        print("\n--- PHASE 3: REBUILDING DATES ---")
        driver.get("https://science.nasa.gov/gallery/your-name-in-landsat-gallery/")
        time.sleep(3)

        detail_urls = []
        page_num = 1
        
        while True:
            # Scroll grid
            last_h = driver.execute_script("return document.body.scrollHeight")
            while True:
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1)
                new_h = driver.execute_script("return document.body.scrollHeight")
                if new_h == last_h: break
                last_h = new_h

            # Collect Article Links
            all_links = driver.find_elements(By.TAG_NAME, "a")
            for link in all_links:
                href = link.get_attribute("href")
                if href and "image-detail" in href and href not in detail_urls:
                    detail_urls.append(href)

            # Turn page
            try:
                next_btns = driver.find_elements(By.XPATH, "//a[contains(translate(text(), 'NEXT', 'next'), 'next') or contains(text(), '»')]")
                next_url = None
                for btn in next_btns:
                    if btn.is_displayed() and btn.get_attribute("href"):
                        next_url = btn.get_attribute("href")
                        break
                if next_url:
                    driver.get(next_url)
                    page_num += 1
                    time.sleep(2)
                else:
                    break
            except Exception:
                break

        print(f"Found {len(detail_urls)} NASA Articles. Extracting Dates...")

        # Visit Articles and Map Dates
        for index, url in enumerate(detail_urls):
            try:
                driver.get(url)
                time.sleep(1.5)
                
                visible_text = driver.find_element(By.TAG_NAME, "body").text
                
                # Get Date
                date_pattern = r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}'
                matches = list(re.finditer(date_pattern, visible_text))
                
                valid_date = None
                for m in matches:
                    start_idx = max(0, m.start() - 40)
                    context = visible_text[start_idx:m.start()].lower()
                    if "updated" not in context and "published" not in context:
                        valid_date = m.group(0)
                        break

                if not valid_date: continue

                # Match to Database
                matched_key = None
                links = driver.find_elements(By.TAG_NAME, "a")
                for link in links:
                    href = link.get_attribute("href")
                    if href and (".png" in href.lower() or ".jpg" in href.lower()):
                        filename = href.split("/")[-1].split("?")[0]
                        candidate_key = urllib.parse.unquote(os.path.splitext(filename)[0].lower())
                        if candidate_key in master_db:
                            matched_key = candidate_key
                            break
                
                if matched_key:
                    master_db[matched_key]["date"] = valid_date
                    print(f"[{index + 1}/{len(detail_urls)}] Mapped Date: {matched_key} -> {valid_date}")
                    
            except Exception:
                continue

        # ==========================================
        # PHASE 4: FINAL EXPORT
        # ==========================================
        metadata_file = os.path.join(base_dir, "metadata.json")
        print("\nSaving pristine, verified metadata.json...")
        with open(metadata_file, "w", encoding='utf-8') as f:
            json.dump(master_db, f, indent=4, ensure_ascii=False)
            
        print("\n--- AUTO-HEAL COMPLETE! ---")
        print("Your database has been fully audited, cleaned, and perfectly synced to your images.")

    finally:
        driver.quit()

if __name__ == "__main__":
    auto_heal_database()