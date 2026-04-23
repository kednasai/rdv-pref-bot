"""
rdv-prefecture-bot — French prefecture RDV slot monitor.

Monitors a prefecture online booking page for newly released appointment slots,
automatically solves the CAPTCHAs that gate access, and triggers an audio alarm
when slots appear so a human can complete the booking manually.

Author: kednasai
Usage:   see README.md and .env.example
"""

import os
import time
import random
import subprocess

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
import deathbycaptcha


# --- CONFIGURATION -----------------------------------------------------------

# Credentials for DeathByCaptcha are read from environment.
DBC_USERNAME = os.environ.get("DBC_USERNAME")
DBC_PASSWORD = os.environ.get("DBC_PASSWORD")

# Target booking URL (override via env).
URL = os.environ.get(
    "RDV_URL",
    "https://www.rdv-prefecture.interieur.gouv.fr/rdvpref/reservation/demarche/9040/",
)

# Chrome major version for undetected_chromedriver. Set this to match the
# Chrome/Chromium installed on the machine running the script.
CHROME_VERSION_MAIN = int(os.environ.get("CHROME_VERSION_MAIN", "140"))

# Path to the audio file played on slot-found alarm. Any format paplay supports.
ALARM_FILE = os.environ.get("ALARM_FILE", "alarm.mp3")

# Polling interval between full attempts (seconds). Randomized in this range so
# the traffic pattern is not perfectly periodic.
POLL_MIN_SECONDS = 240
POLL_MAX_SECONDS = 360

# How many times the inner solver loop will try to get past chained CAPTCHAs
# on a single attempt before giving up and re-queuing.
MAX_SOLVE_ATTEMPTS = 5

# Time to wait for page DOM to settle after navigation / form submission.
PAGE_SETTLE_SECONDS = 2

# --- SELECTORS ---------------------------------------------------------------
# These are the DOM hooks the bot depends on. If the prefecture site is
# redesigned, these are the first things to re-check.

CAPTCHA_IMAGE_SELECTOR = "div.captcha img"
INPUT_FIELD_SELECTOR = "input#captchaFormulaireExtInput"
RECAPTCHA_CHECKBOX_SELECTOR = "div.g-recaptcha"
SUBMIT_BUTTON_XPATH = "//span[contains(text(), 'Suivant')]"
NO_SLOTS_XPATH = "//*[contains(text(), 'Aucun créneau disponible')]"


# --- MAIN --------------------------------------------------------------------

def main():
    if not DBC_USERNAME or not DBC_PASSWORD:
        raise SystemExit(
            "Missing DBC_USERNAME / DBC_PASSWORD. "
            "Copy .env.example to .env and fill them in, or export them."
        )

    print("--- Starting RDV prefecture bot ---")
    print(f"Target: {URL}")

    driver = None
    try:
        driver = uc.Chrome(use_subprocess=True, version_main=CHROME_VERSION_MAIN)
        client = deathbycaptcha.HttpClient(DBC_USERNAME, DBC_PASSWORD)
        print(f"DeathByCaptcha balance: ${client.get_balance()}")

        # --- OUTER LOOP: one full attempt per iteration. ---------------------
        while True:
            try:
                print("\n--- New attempt ---")
                driver.get(URL)

                # --- INNER LOOP: resolve chained CAPTCHAs up to a limit. -----
                for attempt in range(MAX_SOLVE_ATTEMPTS):
                    time.sleep(PAGE_SETTLE_SECONDS)
                    print(f"Analyzing page state ({attempt + 1}/{MAX_SOLVE_ATTEMPTS})...")

                    # STATE 1 — terminal "no slots" page.
                    if driver.find_elements(By.XPATH, NO_SLOTS_XPATH):
                        print("No slots this attempt.")
                        break

                    # STATE 2 — reCAPTCHA gate.
                    if driver.find_elements(By.CSS_SELECTOR, RECAPTCHA_CHECKBOX_SELECTOR):
                        print("reCAPTCHA detected. Solving...")
                        recaptcha = driver.find_element(
                            By.CSS_SELECTOR, RECAPTCHA_CHECKBOX_SELECTOR
                        )
                        site_key = recaptcha.get_attribute("data-sitekey")
                        response_token = client.decode(
                            sitekey=site_key, url=driver.current_url
                        )
                        if not response_token:
                            print("reCAPTCHA solve failed.")
                            break
                        print("reCAPTCHA solved. Submitting.")
                        driver.execute_script(
                            "document.getElementById('g-recaptcha-response').innerHTML = arguments[0];",
                            response_token["text"],
                        )
                        time.sleep(1)
                        driver.find_element(By.XPATH, SUBMIT_BUTTON_XPATH).click()
                        continue

                    # STATE 3 — image CAPTCHA gate.
                    if driver.find_elements(By.CSS_SELECTOR, CAPTCHA_IMAGE_SELECTOR):
                        print("Image CAPTCHA detected. Solving...")
                        captcha_element = driver.find_element(
                            By.CSS_SELECTOR, CAPTCHA_IMAGE_SELECTOR
                        )
                        captcha_file = "captcha.png"
                        captcha_element.screenshot(captcha_file)
                        response = client.decode(captcha_file)
                        if not (response and response.get("text")):
                            print("Image CAPTCHA solve failed.")
                            break
                        code = response["text"].upper()
                        print(f"Image CAPTCHA solved: {code!r}. Submitting.")
                        driver.find_element(By.CSS_SELECTOR, INPUT_FIELD_SELECTOR).send_keys(code)
                        time.sleep(1)
                        driver.find_element(By.XPATH, SUBMIT_BUTTON_XPATH).click()
                        continue

                    # STATE 4 — none of the known gates found. Assume slots.
                    print("Potential success — no known failure or CAPTCHA elements found.")
                    raise SystemExit("Slots found — sounding alarm.")

                else:
                    # The for-loop exhausted without break: unresolved state.
                    print(f"Could not resolve page state in {MAX_SOLVE_ATTEMPTS} tries. Re-queuing.")

            except SystemExit:
                # Raised on success — break out of both loops into the alarm.
                print("\nSlots found. Alarm will ring until you kill the process (Ctrl+C).")
                while True:
                    subprocess.run(["paplay", ALARM_FILE])
                    time.sleep(1)

            except Exception as e:
                print(f"Attempt failed with exception: {e}")

            wait = random.randint(POLL_MIN_SECONDS, POLL_MAX_SECONDS)
            print(f"Sleeping {wait // 60}m {wait % 60}s before next attempt...")
            time.sleep(wait)

    except KeyboardInterrupt:
        print("\nStopped by user.")
    except Exception as e:
        print(f"\nCritical error: {e}")
    finally:
        if driver:
            driver.quit()
        print("--- Bot finished ---")


if __name__ == "__main__":
    main()
