import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

def wake_up_apps():
    urls = [
        "https://dilsalud.streamlit.app",
        "https://dilsalud-tv.streamlit.app",
        "https://dilsalud-dashboard.streamlit.app"
    ]
    
    print("Starting keep-awake script...")
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    try:
        driver = webdriver.Chrome(options=options)
    except Exception as e:
        print("Failed to initialize Chrome Driver:", e)
        return
        
    for url in urls:
        print(f"\nNavigating to {url}...")
        try:
            driver.get(url)
            # Give it some seconds to load the DOM shell
            time.sleep(6)
            
            # Check for the Streamlit Community Cloud sleep screen button
            buttons = driver.find_elements(By.XPATH, "//button[contains(., 'Yes, get this app back up!')]")
            if buttons:
                print(f"-> Found sleeping app screen on {url}. Clicking wake up button...")
                buttons[0].click()
                print("-> Clicked! Waiting 15 seconds to let the server spin up...")
                time.sleep(15)
                print("-> Signal sent successfully.")
            else:
                print("-> App appears to be awake (or the button is not present).")
        except Exception as e:
            print(f"-> Error checking {url}: {e}")
            
    driver.quit()
    print("\nDone!")

if __name__ == "__main__":
    wake_up_apps()
