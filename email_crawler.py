from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import os
import logging
import tempfile

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def setup_chrome_driver():
    try:
        # Chrome options
        chrome_options = Options()
        
        # Create a temporary directory for Chrome profile
        temp_dir = tempfile.mkdtemp()
        logger.info(f"Created temporary Chrome profile at: {temp_dir}")
        chrome_options.add_argument(f'user-data-dir={temp_dir}')
        
        # Additional options to avoid detection
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Use existing Chrome installation
        driver = webdriver.Chrome(options=chrome_options)
        logger.info("Chrome driver initialized successfully")
        
        # Execute CDP commands to prevent detection
        driver.execute_cdp_cmd('Network.setUserAgentOverride', {
            "userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
        })
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        return driver
    except Exception as e:
        logger.error(f"Error setting up Chrome driver: {str(e)}")
        raise

def extract_emails(driver, url):
    try:
        # Navigate to the page
        logger.info(f"Navigating to URL: {url}")
        driver.get(url)
        
        # Wait for the page to load
        logger.info("Waiting for page to load...")
        time.sleep(5)
        
        # Print page title and URL for debugging
        logger.info(f"Current page title: {driver.title}")
        logger.info(f"Current URL: {driver.current_url}")
        
        # Try different selectors for email elements
        selectors = [
            '[data-email]',
            '.email-address',
            'a[href^="mailto:"]',
            'span[data-email]',
            'div[data-email]'
        ]
        
        emails = []
        for selector in selectors:
            logger.info(f"Trying selector: {selector}")
            try:
                # Wait for elements
                wait = WebDriverWait(driver, 10)
                elements = wait.until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector))
                )
                
                # Extract emails
                for element in elements:
                    email = element.get_attribute('data-email') or element.get_attribute('href')
                    if email:
                        if email.startswith('mailto:'):
                            email = email[7:]  # Remove 'mailto:' prefix
                        if '@' in email and email not in emails:
                            emails.append(email)
                            logger.info(f"Found email: {email}")
            except Exception as e:
                logger.warning(f"No elements found with selector {selector}: {str(e)}")
                continue
        
        # If no emails found, try to get page source for debugging
        if not emails:
            logger.info("No emails found. Page source:")
            logger.info(driver.page_source[:1000])  # Print first 1000 chars of page source
            
        return emails
    except Exception as e:
        logger.error(f"Error extracting emails: {str(e)}")
        return []

def main():
    # URL of the page containing emails
    url = "https://contacts.google.com/directory"
    
    try:
        # Setup Chrome driver
        logger.info("Setting up Chrome driver...")
        driver = setup_chrome_driver()
        
        # Extract emails
        logger.info("Starting email extraction...")
        emails = extract_emails(driver, url)
        
        # Print results
        print("\nFound emails:")
        for email in emails:
            print(email)
            
        # Save to file
        with open('emails.txt', 'w', encoding='utf-8') as file:
            for email in emails:
                file.write(email + '\n')
                
        print(f"\nTotal emails found: {len(emails)}")
        print("Emails have been saved to emails.txt")
        
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        
    finally:
        # Close the browser
        if 'driver' in locals():
            driver.quit()
            logger.info("Browser closed")

if __name__ == "__main__":
    main()