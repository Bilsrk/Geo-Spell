import os
import time
import requests
from urllib.parse import unquote
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

def download_landsat_images():
    base_dir = "nasa_alphabet_database"
    if not os.path.exists(base_dir):
        os.makedirs(base_dir)

    print("Launching Image Downloader...")
    
    # Setup Headless Chrome
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    try:
        driver.get("https://science.nasa.gov/mission/landsat/outreach/your-name-in-landsat/")
        time.sleep(3)

        print("Opening accordions to reveal high-res download links...")
        driver.execute_script("""
            document.querySelectorAll('details').forEach(d => d.setAttribute('open', 'true'));
            document.querySelectorAll('button').forEach(b => {
                if(b.getAttribute('aria-expanded') === 'false') b.click();
            });
        """)
        time.sleep(2)

        # Scroll to load the entire DOM
        last_h = driver.execute_script("return document.body.scrollHeight")
        while True:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
            new_h = driver.execute_script("return document.body.scrollHeight")
            if new_h == last_h: break
            last_h = new_h

        # Extract only the high-res download links
        anchors = driver.find_elements(By.TAG_NAME, "a")
        download_links = []
        
        for a in anchors:
            try:
                href = a.get_attribute("href")
                if href and ("png" in href.lower() or "jpg" in href.lower() or "jpeg" in href.lower()):
                    text = (a.text or "").strip().lower()
                    if text == "download":
                        download_links.append(href)
            except Exception:
                continue

        # Remove duplicates while preserving order
        download_links = list(dict.fromkeys(download_links))
        print(f"Found {len(download_links)} high-res images to download.")

        downloaded_count = 0
        for href in download_links:
            # Extract filename and decode URL characters
            filename = unquote(href.split("/")[-1].split("?")[0])
            
            # The primary key always starts with the letter (e.g., "a-0-hickman...")
            letter = filename[0].upper()
            if not letter.isalpha():
                continue
                
            # Create the specific letter folder (e.g., nasa_alphabet_database/A/)
            letter_folder = os.path.join(base_dir, letter)
            os.makedirs(letter_folder, exist_ok=True)
            
            filepath = os.path.join(letter_folder, filename)
            
            # Download the image if it isn't already saved
            if not os.path.exists(filepath):
                print(f"Downloading: {filename} -> {letter}/")
                response = requests.get(href, stream=True)
                if response.status_code == 200:
                    with open(filepath, 'wb') as f:
                        for chunk in response.iter_content(1024):
                            f.write(chunk)
                    downloaded_count += 1
            else:
                print(f"Already exists: {filename}")

        print(f"\nSuccessfully downloaded {downloaded_count} new images.")
        print("Image asset population complete!")

    finally:
        driver.quit()

if __name__ == "__main__":
    download_landsat_images()