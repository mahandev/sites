"""
COMPLETE BUSINESS WEBSITE DATA SCRAPER V3
Gets ALL information needed to build a professional business website.
Works for any industry and area using a centralized command interface.
"""

import time
import json
import re
import os
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from urllib.parse import quote
import logging
import traceback
import argparse

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('business_scraper_v3.log'),
        logging.StreamHandler()
    ]
)

class BusinessWebsiteDataScraper:
    """
    Comprehensive scraper for business website data.
    Extracts ALL information needed for a professional business website:
    - Business info (name, address, phone, hours)
    - Visual content (ALL photos)
    - Social proof (reviews, ratings)
    - Services & amenities
    - Social media links
    """
    
    def __init__(self, filter_mode='no_website'):
        self.output_dir = "business_website_data"
        self.filter_mode = filter_mode  # 'no_website', 'with_website', or 'all'
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(f"{self.output_dir}/images", exist_ok=True)
        self.businesses_data = []
        self.setup_driver()
        
    def setup_driver(self):
        """Setup Chrome with anti-detection"""
        chrome_options = Options()
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
        
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': 'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'
        })
        self.wait = WebDriverWait(self.driver, 15)
        logging.info("✓ Browser initialized")

    def safe_click(self, element):
        """Click element using multiple methods"""
        try:
            element.click()
            return True
        except:
            try:
                self.driver.execute_script("arguments[0].click();", element)
                return True
            except:
                try:
                    ActionChains(self.driver).move_to_element(element).click().perform()
                    return True
                except:
                    return False

    def scroll_and_load_results(self):
        """Scroll the results panel to load all businesses."""
        logging.info("Loading all business results...")
        
        try:
            panel = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div[role="feed"]')))
        except:
            logging.error("Could not find results panel")
            return
        
        last_count = 0
        no_change_count = 0
        
        while no_change_count < 3:
            self.driver.execute_script("arguments[0].scrollTo(0, arguments[0].scrollHeight);", panel)
            time.sleep(2)
            
            results = self.driver.find_elements(By.CSS_SELECTOR, 'a[href*="/maps/place/"]')
            
            if len(results) == last_count:
                no_change_count += 1
            else:
                no_change_count = 0
                last_count = len(results)
                logging.info(f"Found {last_count} businesses...")
        
        logging.info(f"✓ Total businesses found: {last_count}")

    def get_business_links(self):
        """Get unique Google Maps business links."""
        links = set()
        elements = self.driver.find_elements(By.CSS_SELECTOR, 'a[href*="/maps/place/"]')
        for elem in elements:
            try:
                href = elem.get_attribute('href')
                if href and '/maps/place/' in href:
                    links.add(href)
            except:
                continue
        return list(links)

    def scrape_business_complete(self, url):
        """
        Scrape COMPLETE business data for website building.
        """
        logging.info(f"\n{'='*70}")
        logging.info(f"SCRAPING: {url[:80]}...")
        logging.info(f"{'='*70}")
        
        business = {
            'google_maps_url': url,
            'scraped_at': datetime.now().isoformat(),
            
            # Basic Business Info
            'name': None,
            'tagline': None,
            'category': None,
            'rating': None,
            'total_reviews': None,
            'price_level': None,
            
            # Contact Info
            'address': None,
            'full_address': None,
            'plus_code': None,
            'phone': None,
            'website': None,
            'has_website': False,
            
            # Hours (CRITICAL)
            'hours': {},
            'hours_raw': None,
            'is_open_now': None,
            
            # Services & Amenities
            'service_options': [],
            'amenities': [],
            'accessibility': [],
            'atmosphere': [],
            'payments': [],
            'offerings': [],
            'highlights': [],
            
            # Visual Content
            'photos': [],
            'photos_count': 0,
            'cover_photo': None,
            
            # Social Proof
            'reviews': [],
            'review_highlights': [],
            
            # Social Media
            'social_media': {},
            
            # Additional
            'description': None,
            'popular_times': None,
        }
        
        try:
            self.driver.get(url)
            time.sleep(4)
            
            # ========================================
            # 1. BASIC INFO
            # ========================================
            self._extract_basic_info(business)
            
            # Filter based on website presence
            if self.filter_mode == 'no_website' and business['has_website']:
                logging.info(f"Skipping - has website: {business['website']}")
                return None
            elif self.filter_mode == 'with_website' and not business['has_website']:
                logging.info(f"Skipping - no website found")
                return None
            
            # ========================================
            # 2. HOURS (CRITICAL!)
            # ========================================
            self._extract_hours(business)
            
            # ========================================
            # 3. ABOUT TAB - Services & Amenities
            # ========================================
            self._extract_about_section(business)
            
            # ========================================
            # 4. ALL PHOTOS
            # ========================================
            self.driver.get(url)
            time.sleep(2)
            self._extract_all_photos(business)
            
            # ========================================
            # 5. REVIEWS
            # ========================================
            self.driver.get(url)
            time.sleep(2)
            self._extract_reviews(business)
            
            # ========================================
            # 6. SOCIAL MEDIA & LINKS
            # ========================================
            self._extract_social_media(business)
            
            # Print summary
            self._print_summary(business)
            
            return business
            
        except Exception as e:
            logging.error(f"Error scraping business: {e}")
            traceback.print_exc()
            return None

    def _extract_basic_info(self, business):
        """Extract all basic business information"""
        logging.info("Extracting basic info...")
        
        # Name
        try:
            name_elem = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'h1.DUwDvf')))
            business['name'] = name_elem.text
            logging.info(f"  Name: {business['name']}")
        except:
            business['name'] = "Unknown Business"

        # Category
        try:
            category_elem = self.driver.find_element(By.CSS_SELECTOR, 'button.DkEaL')
            business['category'] = category_elem.text.strip() or None
        except:
            pass
        
        # Rating
        try:
            rating_elem = self.driver.find_element(By.CSS_SELECTOR, 'div.F7nice span[aria-hidden="true"]')
            business['rating'] = rating_elem.text
            logging.info(f"  Rating: {business['rating']}")
        except:
            pass
        
        # Total Reviews
        try:
            reviews_elem = self.driver.find_element(By.CSS_SELECTOR, 'span[aria-label*="reviews"]')
            text = reviews_elem.get_attribute('aria-label')
            match = re.search(r'([\d,]+)', text)
            business['total_reviews'] = match.group(1).replace(',', '') if match else None
            logging.info(f"  Total Reviews: {business['total_reviews']}")
        except:
            pass
        
        # Check for website FIRST
        try:
            website_elem = self.driver.find_element(By.CSS_SELECTOR, 'a[data-item-id="authority"]')
            business['website'] = website_elem.get_attribute('href')
            business['has_website'] = True
            return  # Exit early if has website
        except:
            business['has_website'] = False
        
        # Address
        try:
            addr_elem = self.driver.find_element(By.CSS_SELECTOR, 'button[data-item-id="address"]')
            full_addr = addr_elem.get_attribute('aria-label')
            business['full_address'] = full_addr.replace('Address: ', '').strip()
            business['address'] = business['full_address']
            logging.info(f"  Address: {business['address'][:50]}...")
        except:
            pass
        
        # Phone
        try:
            phone_elem = self.driver.find_element(By.CSS_SELECTOR, 'button[data-item-id^="phone:tel:"]')
            phone_text = phone_elem.get_attribute('aria-label')
            business['phone'] = phone_text.replace('Phone: ', '').strip()
            logging.info(f"  Phone: {business['phone']}")
        except:
            pass
        
        # Plus Code
        try:
            plus_elem = self.driver.find_element(By.CSS_SELECTOR, 'button[data-item-id="oloc"]')
            business['plus_code'] = plus_elem.get_attribute('aria-label').replace('Plus code: ', '').strip()
        except:
            pass

    def _extract_hours(self, business):
        """Extract operating hours for the business."""
        logging.info("Extracting hours...")
        
        hours = {}
        days_order = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
        
        try:
            # First scroll down to make sure hours section is visible
            self.driver.execute_script("window.scrollBy(0, 300);")
            time.sleep(1)
            
            # STEP 1: Find the hours row - it shows "Closed · Opens X am" or "Open · Closes X pm"
            # Look for the CLICKABLE element that has hours info
            hours_row = None
            
            # The hours row in Google Maps has aria-label containing "hours"
            # Or contains text like "Closed" / "Open" with times
            
            # Try finding by aria-label first
            try:
                hours_row = self.driver.find_element(By.CSS_SELECTOR, '[data-item-id="oh"]')
                logging.info(f"  Found hours via data-item-id='oh'")
            except:
                pass
            
            # If not found, look for element containing "Opens" or "Closes"
            if not hours_row:
                try:
                    # Find spans/divs with opening hours text
                    elements = self.driver.find_elements(By.XPATH, 
                        "//*[contains(text(), 'Opens ') or contains(text(), 'Closes ') or contains(text(), 'Open 24 hours') or contains(text(), 'Open ⋅') or contains(text(), 'Closed ⋅')]"
                    )
                    for elem in elements:
                        # Check if this looks like the hours row (not in reviews etc)
                        text = elem.text
                        if ('Opens' in text or 'Closes' in text or 'Open' in text or 'Closed' in text):
                            # Try to get the clickable parent
                            try:
                                hours_row = elem.find_element(By.XPATH, './ancestor::div[@data-item-id="oh"]')
                                logging.info(f"  Found hours row via ancestor")
                                break
                            except:
                                # The element itself might be clickable
                                hours_row = elem
                                logging.info(f"  Using element directly: '{text[:50]}'")
                                break
                except Exception as e:
                    logging.debug(f"  Error finding hours text: {e}")
            
            if not hours_row:
                logging.warning("  ✗ Could not find hours element")
                return
            
            # Get the visible text before clicking
            try:
                dropdown_text = hours_row.text
                business['hours_raw'] = dropdown_text
                logging.info(f"  Hours element text: '{dropdown_text}'")
                
                # Determine if currently open
                if 'closed' in dropdown_text.lower():
                    business['is_open_now'] = False
                elif 'open' in dropdown_text.lower():
                    business['is_open_now'] = True
            except:
                pass
            
            # STEP 2: Click to expand the hours table
            logging.info("  Clicking to expand hours...")
            
            # Try multiple click methods
            clicked = False
            try:
                # Try JS click first (most reliable)
                self.driver.execute_script("arguments[0].click();", hours_row)
                clicked = True
                logging.info("  Clicked via JS")
            except:
                pass
            
            if not clicked:
                try:
                    hours_row.click()
                    clicked = True
                    logging.info("  Clicked directly")
                except:
                    pass
            
            if not clicked:
                try:
                    ActionChains(self.driver).move_to_element(hours_row).click().perform()
                    clicked = True
                    logging.info("  Clicked via ActionChains")
                except:
                    logging.error("  Failed all click methods")
                    return
            
            # Wait for hours table to appear
            time.sleep(2.5)
            
            # STEP 3: Find and parse the TABLE element containing hours
            logging.info("  Looking for hours table...")
            
            # The hours are in a <table> element that appears after clicking
            table = None
            
            # Try to find the table
            try:
                # Wait for any table to appear
                table = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.TAG_NAME, 'table'))
                )
                logging.info("  Found a table element")
            except:
                # Try alternative selectors
                for selector in ['table.eK4R0e', 'table.WgFkxc', 'table.y0skZc']:
                    try:
                        table = self.driver.find_element(By.CSS_SELECTOR, selector)
                        logging.info(f"  Found table: {selector}")
                        break
                    except:
                        continue
            
            if table:
                # Parse the table
                logging.info("  Parsing hours table...")
                rows = table.find_elements(By.TAG_NAME, 'tr')
                logging.info(f"  Found {len(rows)} rows")
                
                for row in rows:
                    try:
                        row_text = row.text.strip()
                        if not row_text:
                            continue
                            
                        logging.info(f"    Row: '{row_text}'")
                        
                        # Match day names
                        for day in days_order:
                            if day in row_text:
                                # Get the time part (everything after the day name)
                                # Try getting from cells first
                                cells = row.find_elements(By.TAG_NAME, 'td')
                                if len(cells) >= 2:
                                    time_text = cells[1].text.strip()
                                else:
                                    time_text = row_text.replace(day, '').strip()
                                
                                if time_text:
                                    hours[day] = time_text
                                    logging.info(f"    ✓ {day}: {time_text}")
                                break
                    except Exception as re:
                        continue
            else:
                logging.warning("  No table found, trying fallback...")
                
                # Fallback: Get text from the expanded area
                try:
                    # After clicking, the hours might appear in the same element
                    expanded_text = hours_row.text
                    logging.info(f"  Expanded text: '{expanded_text[:200]}'")
                    
                    # Parse line by line
                    for line in expanded_text.split('\n'):
                        line = line.strip()
                        for day in days_order:
                            if day in line:
                                time_part = line.replace(day, '').strip()
                                if time_part and ('am' in time_part.lower() or 'pm' in time_part.lower() or 'closed' in time_part.lower()):
                                    hours[day] = time_part
                                    logging.info(f"    {day}: {time_part}")
                                break
                except:
                    pass
            
        except Exception as e:
            logging.error(f"  Hours extraction error: {e}")
        
        business['hours'] = hours
        
        if hours:
            logging.info(f"  ✓ Hours extracted: {len(hours)} days")
        else:
            logging.warning(f"  ✗ Could not extract hours")

    def _extract_about_section(self, business):
        """Extract all info from About tab - services, amenities, etc."""
        logging.info("Extracting About section...")
        
        try:
            # Click About tab using discovered selector
            about_tab = None
            about_selectors = [
                (By.XPATH, '//div[text()="About"]'),
                (By.XPATH, '//button[text()="About"]'),
                (By.CSS_SELECTOR, 'button.hh2c6[aria-label*="About"]'),
                (By.XPATH, '//*[@role="tab" and contains(., "About")]')
            ]
            
            for by, sel in about_selectors:
                try:
                    about_tab = self.driver.find_element(by, sel)
                    if about_tab:
                        logging.info(f"  Found About tab")
                        break
                except:
                    continue
            
            if about_tab:
                self.safe_click(about_tab)
                time.sleep(3)
                logging.info("  Clicked About tab")
                
                # Scroll to load all content
                self.driver.execute_script("window.scrollTo(0, 500);")
                time.sleep(1)
                
                # Find all sections with aria-label
                sections = self.driver.find_elements(By.XPATH, '//*[@aria-label]')
                
                for section in sections:
                    try:
                        label = (section.get_attribute('aria-label') or '').lower()
                        
                        # Service Options
                        if 'service option' in label:
                            items = self._extract_section_items(section)
                            business['service_options'].extend(items)
                            logging.info(f"    Service Options: {items}")
                        
                        # Accessibility
                        elif 'accessibility' in label:
                            items = self._extract_section_items(section)
                            business['accessibility'].extend(items)
                            logging.info(f"    Accessibility: {items}")
                        
                        # Amenities
                        elif 'amenities' in label:
                            items = self._extract_section_items(section)
                            business['amenities'].extend(items)
                            logging.info(f"    Amenities: {items}")
                        
                        # Atmosphere
                        elif 'atmosphere' in label:
                            items = self._extract_section_items(section)
                            business['atmosphere'].extend(items)
                            logging.info(f"    Atmosphere: {items}")
                        
                        # Payments
                        elif 'payment' in label:
                            items = self._extract_section_items(section)
                            business['payments'].extend(items)
                            logging.info(f"    Payments: {items}")
                        
                        # Offerings
                        elif 'offering' in label:
                            items = self._extract_section_items(section)
                            business['offerings'].extend(items)
                            logging.info(f"    Offerings: {items}")
                        
                        # Highlights
                        elif 'highlight' in label:
                            items = self._extract_section_items(section)
                            business['highlights'].extend(items)
                            logging.info(f"    Highlights: {items}")
                            
                    except Exception as e:
                        continue
                
                # Also look for individual amenity spans
                try:
                    amenity_spans = self.driver.find_elements(By.CSS_SELECTOR, 'span[aria-label]')
                    for span in amenity_spans:
                        aria = span.get_attribute('aria-label') or ''
                        if any(kw in aria.lower() for kw in ['has', 'offers', 'available', 'accepts']):
                            # Clean up the text
                            feature = aria.replace('Has ', '').replace('Offers ', '').replace('Accepts ', '').strip()
                            if feature and feature not in business['amenities']:
                                business['amenities'].append(feature)
                except:
                    pass
                
        except Exception as e:
            logging.error(f"  About section error: {e}")
        
        # Deduplicate
        for key in ['service_options', 'amenities', 'accessibility', 'atmosphere', 'payments', 'offerings', 'highlights']:
            business[key] = list(set(business[key]))
        
        total_features = sum(len(business[k]) for k in ['service_options', 'amenities', 'accessibility', 'atmosphere', 'payments', 'offerings', 'highlights'])
        logging.info(f"  ✓ Total features extracted: {total_features}")

    def _extract_section_items(self, section):
        """Extract items from a section"""
        items = []
        
        try:
            # Look for list items
            li_elements = section.find_elements(By.CSS_SELECTOR, 'li, span')
            for li in li_elements:
                text = li.text.strip()
                aria = li.get_attribute('aria-label') or ''
                
                # Use aria-label if it has "Has" pattern
                if 'has' in aria.lower() or 'offers' in aria.lower():
                    feature = aria.replace('Has ', '').replace('Offers ', '').strip()
                    if feature and len(feature) > 2:
                        items.append(feature)
                elif text and len(text) > 2 and len(text) < 60:
                    # Filter out section headers
                    if not any(kw in text.lower() for kw in ['service option', 'accessibility', 'amenities', 'atmosphere', 'payment']):
                        items.append(text)
        except:
            pass
        
        return list(set(items))

    def _extract_all_photos(self, business):
        """Extract ALL photos from the gallery"""
        logging.info("Extracting all photos...")
        
        photo_urls = set()
        
        try:
            # Click on photos - using discovered selector
            photo_clicked = False
            photo_selectors = [
                'button[aria-label*="Photo"]',
                'button[aria-label*="photo"]',
                'img[src*="googleusercontent"]',
            ]
            
            for sel in photo_selectors:
                try:
                    elem = self.driver.find_element(By.CSS_SELECTOR, sel)
                    if elem:
                        self.safe_click(elem)
                        time.sleep(3)
                        photo_clicked = True
                        logging.info("  Opened photo gallery")
                        break
                except:
                    continue
            
            if not photo_clicked:
                logging.warning("  Could not open photo gallery")
                return
            
            # Collect all photos by navigating through gallery
            prev_count = 0
            stale = 0
            
            for attempt in range(100):  # Get up to 100 photos
                # Collect current photos
                imgs = self.driver.find_elements(By.CSS_SELECTOR, 'img[src*="googleusercontent"], img[src*="ggpht"]')
                
                for img in imgs:
                    try:
                        src = img.get_attribute('src')
                        if src and ('googleusercontent' in src or 'ggpht' in src):
                            # Convert to high resolution
                            high_res = re.sub(r'=w\d+-h\d+', '=w1920-h1080', src)
                            high_res = re.sub(r'=s\d+', '=s1920', high_res)
                            photo_urls.add(high_res)
                    except:
                        continue
                
                # Check progress
                if len(photo_urls) == prev_count:
                    stale += 1
                    if stale >= 5:
                        break
                else:
                    stale = 0
                    prev_count = len(photo_urls)
                    if attempt % 10 == 0:
                        logging.info(f"    Found {len(photo_urls)} photos...")
                
                # Navigate to next photo
                try:
                    next_btn = self.driver.find_element(By.CSS_SELECTOR, 'button[aria-label*="Next"]')
                    self.safe_click(next_btn)
                    time.sleep(0.3)
                except:
                    try:
                        # Try arrow key
                        body = self.driver.find_element(By.TAG_NAME, 'body')
                        body.send_keys('\ue014')  # Right arrow
                        time.sleep(0.3)
                    except:
                        break
            
            # Close gallery
            try:
                close_btn = self.driver.find_element(By.CSS_SELECTOR, 'button[aria-label="Close"], button[aria-label="Back"]')
                self.safe_click(close_btn)
            except:
                try:
                    self.driver.back()
                except:
                    pass
            
        except Exception as e:
            logging.error(f"  Photo extraction error: {e}")
        
        business['photos'] = list(photo_urls)
        business['photos_count'] = len(photo_urls)
        
        if photo_urls:
            business['cover_photo'] = business['photos'][0]
            logging.info(f"  ✓ Found {len(photo_urls)} photo URLs (stored, not downloaded)")
        else:
            logging.warning("  ✗ No photos found")

    def _extract_reviews(self, business, max_reviews=15):
        """Extract detailed reviews with ratings"""
        logging.info("Extracting reviews...")
        
        reviews = []
        
        try:
            # Click Reviews tab
            reviews_tab = None
            for sel in [
                (By.XPATH, '//button[text()="Reviews"]'),
                (By.XPATH, '//div[text()="Reviews"]'),
                (By.CSS_SELECTOR, 'button[aria-label*="Reviews"]')
            ]:
                try:
                    reviews_tab = self.driver.find_element(sel[0], sel[1])
                    if reviews_tab:
                        break
                except:
                    continue
            
            if reviews_tab:
                self.safe_click(reviews_tab)
                time.sleep(3)
                logging.info("  Clicked Reviews tab")
            
            # Scroll to load more reviews
            for _ in range(5):
                try:
                    panel = self.driver.find_element(By.CSS_SELECTOR, 'div.m6QErb')
                    self.driver.execute_script("arguments[0].scrollBy(0, 800);", panel)
                    time.sleep(1)
                except:
                    self.driver.execute_script("window.scrollBy(0, 800);")
                    time.sleep(1)
            
            # Find review containers
            review_divs = self.driver.find_elements(By.CSS_SELECTOR, 'div.jftiEf, div[data-review-id]')
            logging.info(f"  Found {len(review_divs)} review elements")
            
            for div in review_divs:
                try:
                    review = {}
                    
                    # Expand "More" if present
                    try:
                        more_btn = div.find_element(By.CSS_SELECTOR, 'button.w8nwRe')
                        self.safe_click(more_btn)
                        time.sleep(0.2)
                    except:
                        pass
                    
                    # Author
                    try:
                        author = div.find_element(By.CSS_SELECTOR, 'div.d4r55, button.WEBjve').text
                        review['author'] = author
                    except:
                        review['author'] = "Anonymous"
                    
                    # Rating (stars)
                    try:
                        rating_elem = div.find_element(By.CSS_SELECTOR, 'span.kvMYJc')
                        rating_text = rating_elem.get_attribute('aria-label')
                        match = re.search(r'(\d+)', rating_text)
                        review['rating'] = int(match.group(1)) if match else 5
                    except:
                        review['rating'] = 5
                    
                    # Review text
                    try:
                        text_elem = div.find_element(By.CSS_SELECTOR, 'span.wiI7pd')
                        review['text'] = text_elem.text
                        review['word_count'] = len(review['text'].split())
                    except:
                        review['text'] = ""
                        review['word_count'] = 0
                    
                    # Time posted
                    try:
                        time_elem = div.find_element(By.CSS_SELECTOR, 'span.rsqaWe')
                        review['posted'] = time_elem.text
                    except:
                        review['posted'] = "Recently"
                    
                    # Only keep substantial reviews
                    if review['text'] and len(review['text']) > 20:
                        reviews.append(review)
                    
                except:
                    continue
            
            # Sort by rating (highest) then word count (most detailed)
            reviews.sort(key=lambda x: (x['rating'], x['word_count']), reverse=True)
            reviews = reviews[:max_reviews]
            
        except Exception as e:
            logging.error(f"  Reviews extraction error: {e}")
        
        business['reviews'] = reviews
        
        if reviews:
            logging.info(f"  ✓ Extracted {len(reviews)} quality reviews")
            # Get review highlights (snippets from top reviews)
            business['review_highlights'] = [r['text'][:100] + '...' for r in reviews[:3] if r['text']]
        else:
            logging.warning("  ✗ No reviews found")

    def _extract_social_media(self, business):
        """Extract social media links"""
        logging.info("Extracting social media...")
        
        social = {}
        
        try:
            links = self.driver.find_elements(By.CSS_SELECTOR, 'a[href]')
            
            for link in links:
                try:
                    href = link.get_attribute('href') or ''
                    
                    if 'instagram.com' in href:
                        social['instagram'] = href
                    elif 'facebook.com' in href:
                        social['facebook'] = href
                    elif 'twitter.com' in href or 'x.com' in href:
                        social['twitter'] = href
                    elif 'youtube.com' in href:
                        social['youtube'] = href
                    elif 'linkedin.com' in href:
                        social['linkedin'] = href
                    elif 'wa.link' in href or 'wa.me' in href or 'whatsapp' in href:
                        social['whatsapp'] = href
                except:
                    continue
            
        except Exception as e:
            logging.debug(f"  Social media error: {e}")
        
        business['social_media'] = social
        
        if social:
            logging.info(f"  ✓ Found: {list(social.keys())}")

    def _write_to_new(self, business):
        """Write one JSON file per business into new/ for pipeline pickup."""
        slug = re.sub(r"[^a-z0-9]+", "-", (business.get("name") or "unknown").lower()).strip("-")
        new_dir = os.path.join(self.output_dir, "new")
        os.makedirs(new_dir, exist_ok=True)
        path = os.path.join(new_dir, f"{slug}.json")
        counter = 1
        while os.path.exists(path):
            path = os.path.join(new_dir, f"{slug}-{counter}.json")
            counter += 1
        with open(path, "w", encoding="utf-8") as f:
            json.dump(business, f, indent=2, ensure_ascii=False)
        logging.info(f"  Written to new/: {os.path.basename(path)}")

    def _download_photos(self, business_name, photo_urls):
        """Skip downloading - just log the URLs"""
        # Not downloading photos - just storing URLs
        logging.info(f"  Stored {len(photo_urls)} photo URLs (not downloading)")

    def _print_summary(self, business):
        """Print extraction summary"""
        print(f"\n{'='*60}")
        print(f"SUMMARY: {business['name']}")
        print(f"{'='*60}")
        print(f"Category: {business.get('category')}")
        print(f"Rating: {business['rating']} ({business['total_reviews']} reviews)")
        print(f"Phone: {business['phone']}")
        print(f"Address: {business['address']}")
        print(f"Hours: {len(business['hours'])} days - {'YES' if business['hours'] else 'MISSING'}")
        if business['hours']:
            for day, time in business['hours'].items():
                print(f"   {day}: {time}")
        print(f"Services: {len(business['service_options'])}")
        print(f"Amenities: {len(business['amenities'])}")
        print(f"Payments: {len(business['payments'])}")
        print(f"Photos: {business['photos_count']}")
        print(f"Reviews: {len(business['reviews'])}")
        print(f"Social: {list(business['social_media'].keys())}")
        print(f"{'='*60}\n")

    def run(self, industry, area):
        """Main run method for any industry and area."""
        search_query = f"{industry} in {area}"
        logging.info(f"\nStarting scrape: {search_query}")
        
        url = f"https://www.google.com/maps/search/{quote(search_query)}"
        self.driver.get(url)
        time.sleep(5)
        
        self.scroll_and_load_results()
        business_links = self.get_business_links()
        
        logging.info(f"Found {len(business_links)} businesses to process")
        
        for idx, link in enumerate(business_links, 1):
            logging.info(f"\n\n{'#'*70}")
            logging.info(f"# BUSINESS {idx}/{len(business_links)}")
            logging.info(f"{'#'*70}")
            
            try:
                business = self.scrape_business_complete(link)
                
                if business:
                    self.businesses_data.append(business)
                    self._write_to_new(business)
                    self.save_progress()
                    logging.info(f"Added: {business['name']}")
                
                time.sleep(2)
                
            except KeyboardInterrupt:
                logging.info("⚠️ Interrupted by user")
                break
            except Exception as e:
                logging.error(f"Error: {e}")
                continue
        
        self.save_final()
        
        print(f"\n\n{'='*70}")
        print("SCRAPING COMPLETE")
        print(f"Total businesses scraped: {len(self.businesses_data)}")
        print(f"Data saved in: {self.output_dir}/")
        print(f"{'='*70}")

    def save_progress(self):
        """Save progress"""
        with open(f"{self.output_dir}/businesses_progress.json", 'w', encoding='utf-8') as f:
            json.dump(self.businesses_data, f, indent=2, ensure_ascii=False)

    def save_final(self):
        """Save final data"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Full JSON
        with open(f"{self.output_dir}/businesses_complete_{timestamp}.json", 'w', encoding='utf-8') as f:
            json.dump(self.businesses_data, f, indent=2, ensure_ascii=False)
        
        # Summary CSV
        import csv
        with open(f"{self.output_dir}/businesses_summary_{timestamp}.csv", 'w', newline='', encoding='utf-8') as f:
            fields = ['name', 'rating', 'total_reviews', 'phone', 'address', 'hours_days', 'amenities_count', 'photos_count', 'reviews_count']
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            
            for business in self.businesses_data:
                writer.writerow({
                    'name': business.get('name'),
                    'rating': business.get('rating'),
                    'total_reviews': business.get('total_reviews'),
                    'phone': business.get('phone'),
                    'address': business.get('address'),
                    'hours_days': len(business.get('hours', {})),
                    'amenities_count': len(business.get('amenities', [])),
                    'photos_count': business.get('photos_count', 0),
                    'reviews_count': len(business.get('reviews', []))
                })
        
        logging.info(f"Saved to {self.output_dir}/")

    def close(self):
        """Close browser"""
        self.driver.quit()


def main():
    parser = argparse.ArgumentParser(
        description="Scrape Google Maps businesses without websites for any industry and area."
    )
    parser.add_argument("--industry", type=str, help="Business category, for example: dentists, cafes, salons")
    parser.add_argument("--area", type=str, help="Area or city, for example: pune, mumbai, new york")
    args = parser.parse_args()

    if args.industry and args.area:
        industry = args.industry.strip()
        area = args.area.strip()
    else:
        industry = input("Enter industry/category: ").strip()
        area = input("Enter area/city: ").strip()

    if not industry or not area:
        raise ValueError("Both industry and area are required.")

    print("\nFilter by website presence:")
    print("  1 - Only businesses WITHOUT a website (default)")
    print("  2 - Only businesses WITH a website")
    print("  3 - All businesses")
    filter_choice = input("Choose [1/2/3]: ").strip() or "1"
    filter_map = {"1": "no_website", "2": "with_website", "3": "all"}
    filter_mode = filter_map.get(filter_choice, "no_website")
    logging.info(f"Filter mode: {filter_mode}")

    scraper = BusinessWebsiteDataScraper(filter_mode=filter_mode)
    
    try:
        scraper.run(industry=industry, area=area)
    except KeyboardInterrupt:
        logging.info("Interrupted")
    except Exception as e:
        logging.error(f"Fatal: {e}")
        traceback.print_exc()
    finally:
        scraper.close()


if __name__ == "__main__":
    main()
