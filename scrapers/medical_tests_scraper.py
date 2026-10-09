"""
Fixed Medical Tests Scraper for MedlinePlus
Saves to: data/medical_tests.json
"""

import requests
from bs4 import BeautifulSoup
import json
import time
from urllib.parse import urljoin
import logging
import os

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class FixedMedicalTestsScraper:
    def __init__(self):
        self.base_url = "https://medlineplus.gov/lab-tests"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }
        self.tests_data = []
        self.output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
        os.makedirs(self.output_dir, exist_ok=True)
    
    def fetch_page(self, url, retry_count=3):
        """Fetch page with retry logic"""
        for attempt in range(retry_count):
            try:
                response = requests.get(url, headers=self.headers, timeout=20)
                response.raise_for_status()
                return response.text
            except requests.exceptions.RequestException as e:
                if attempt < retry_count - 1:
                    wait_time = 2 ** attempt
                    logger.warning(f"Retry {attempt + 1} for {url} in {wait_time}s")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Failed to fetch {url}: {e}")
                    return None
    
    def parse_medical_tests_page(self):
        """Parse the main medical tests listing page - UPDATED for new structure"""
        logger.info("Parsing main medical tests page...")
        html = self.fetch_page(self.base_url)
        
        if not html:
            logger.error("Could not fetch main page")
            return []
        
        soup = BeautifulSoup(html, 'html.parser')
        tests_links = []
        
        # STRATEGY 1: Look for alphabetical listing sections
        # MedlinePlus usually has tests listed in divs with class 'mp-content' or 'content'
        content_areas = soup.find_all(['main', 'article', 'div'], class_=[
            'mp-content', 'content', 'main-content', 'page-content', 
            'mp-text', 'text', 'body-content'
        ])
        
        if not content_areas:
            content_areas = [soup]  # Fallback to full soup
        
        for content in content_areas:
            for link in content.find_all('a', href=True):
                href = link.get('href', '')
                test_name = link.get_text(strip=True)
                
                # MedlinePlus test links usually contain '/lab-tests/' and end with .html
                # OR they might be relative like '/lab-tests/a1c-test.html'
                if href and test_name and len(test_name) > 2:
                    is_test_link = False
                    
                    # Pattern 1: Contains /lab-tests/ and not the base page
                    if '/lab-tests/' in href and href != '/lab-tests/' and href != '/lab-tests':
                        is_test_link = True
                    
                    # Pattern 2: Ends with common test page patterns
                    if any(href.endswith(ext) for ext in ['.html', '.htm', '.php']):
                        if '/lab-tests' in href:
                            is_test_link = True
                    
                    if is_test_link:
                        full_url = urljoin(self.base_url, href)
                        # Remove duplicates
                        if not any(t['url'] == full_url for t in tests_links):
                            tests_links.append({
                                'name': test_name,
                                'url': full_url
                            })
        
        # STRATEGY 2: If no links found, try finding all links and filtering
        if len(tests_links) == 0:
            logger.info("Trying alternative parsing strategy...")
            all_links = soup.find_all('a', href=True)
            for link in all_links:
                href = link.get('href', '')
                test_name = link.get_text(strip=True)
                
                # Look for links that go to specific test pages
                if href and '/lab-tests/' in href and href.count('/') > 2:
                    full_url = urljoin(self.base_url, href)
                    if full_url != self.base_url and len(test_name) > 2:
                        if not any(t['url'] == full_url for t in tests_links):
                            tests_links.append({
                                'name': test_name,
                                'url': full_url
                            })
        
        # STRATEGY 3: If still no links, the page might be JavaScript-rendered
        # Try to find JSON data or API endpoints in page source
        if len(tests_links) == 0:
            logger.warning("No links found via HTML parsing. Site may use JavaScript or have changed structure.")
            logger.info("Attempting to find test links from sitemap or alternative sources...")
            
            # Try common MedlinePlus test URLs directly
            common_tests = [
                'a1c-test', 'allergy-blood-test', 'amniocentesis', 'blood-culture',
                'blood-glucose-test', 'blood-pressure-test', 'bmp', 'cbc',
                'chest-x-ray', 'cholesterol-tests', 'covid-19-testing', 'creatinine-test',
                'ct-scan', 'ecg', 'echocardiography', 'electrolyte-panel',
                'ferritin-test', 'flu-test', 'glucose-tolerance-test', 'hba1c',
                'hdl-cholesterol', 'hearing-tests', 'hepatitis-panel', 'hiv-test',
                'kidney-function-tests', 'ldl-cholesterol', 'liver-function-tests',
                'lpa-test', 'lupus-anticoagulant-testing', 'mammography', 'mri',
                'pap-smear', 'pulse-oximetry', 'spirometry', 'stool-culture',
                'thyroid-tests', 'triglycerides-test', 'ultrasound', 'urinalysis',
                'vitamin-d-test', 'x-ray'
            ]
            
            for test_slug in common_tests:
                test_url = f"https://medlineplus.gov/lab-tests/{test_slug}.html"
                tests_links.append({
                    'name': test_slug.replace('-', ' ').title(),
                    'url': test_url
                })
            
            logger.info(f"Using {len(tests_links)} common test URLs as fallback")
        
        logger.info(f"Found {len(tests_links)} test links")
        return tests_links
    
    def extract_test_content(self, soup, test_name):
        """Extract structured content from test page - ROBUST version"""
        test_data = {
            'name': test_name,
            'url': '',
            'description': '',
            'why_done': '',
            'what_happens': '',
            'risks_complications': '',
            'normal_values': '',
            'what_results_mean': '',
            'how_you_prepare': '',
            'special_considerations': ''
        }
        
        try:
            # Find main content area
            main_content = soup.find('main') or soup.find('article') or soup.find('div', id='topic')
            
            if not main_content:
                # Try alternative content selectors
                main_content = soup.find('div', class_='mp-content') or \
                              soup.find('div', class_='content') or \
                              soup.find('div', role='main')
            
            if not main_content:
                return None
            
            # Extract description from first paragraph or summary section
            first_para = main_content.find('p')
            if first_para:
                test_data['description'] = first_para.get_text(strip=True)[:500]
            
            # Find all headings and their following content
            headings = main_content.find_all(['h2', 'h3', 'h4'])
            
            for heading in headings:
                heading_text = heading.get_text(strip=True).lower()
                
                # Get next sibling content until next heading
                content_parts = []
                sibling = heading.find_next_sibling()
                while sibling and sibling.name not in ['h2', 'h3', 'h4']:
                    if sibling.name in ['p', 'li']:
                        text = sibling.get_text(strip=True)
                        if text:
                            content_parts.append(text)
                    sibling = sibling.find_next_sibling()
                
                content = ' '.join(content_parts[:3])  # Take first 3 paragraphs
                
                # Map to fields using keyword matching
                if any(kw in heading_text for kw in ['description', 'overview', 'summary', 'about', 'what is']):
                    test_data['description'] = content or test_data['description']
                
                elif any(kw in heading_text for kw in ['why', 'when', 'purpose', 'reason', 'use']):
                    test_data['why_done'] = content
                
                elif any(kw in heading_text for kw in ['prepare', 'before', 'getting ready']):
                    test_data['how_you_prepare'] = content
                
                elif any(kw in heading_text for kw in ['procedure', 'happen', 'during', 'process', 'how is']):
                    test_data['what_happens'] = content
                
                elif any(kw in heading_text for kw in ['risk', 'complication', 'side effect', 'danger']):
                    test_data['risks_complications'] = content
                
                elif any(kw in heading_text for kw in ['normal', 'range', 'value', 'reference']):
                    test_data['normal_values'] = content
                
                elif any(kw in heading_text for kw in ['result', 'mean', 'understand', 'interpret']):
                    test_data['what_results_mean'] = content
            
            # If still no description, get first 500 chars of main content
            if not test_data['description']:
                all_text = main_content.get_text(separator=' ', strip=True)
                test_data['description'] = all_text[:500] if all_text else ''
            
            return test_data
            
        except Exception as e:
            logger.error(f"Error extracting content for {test_name}: {e}")
            return None
    
    def scrape_single_test(self, test_info):
        """Scrape a single test with error handling"""
        test_name = test_info['name']
        test_url = test_info['url']
        
        try:
            logger.info(f"Scraping: {test_name}")
            html = self.fetch_page(test_url)
            if not html:
                return None
            
            soup = BeautifulSoup(html, 'html.parser')
            test_data = self.extract_test_content(soup, test_name)
            
            if test_data:
                test_data['url'] = test_url
                return test_data
            else:
                logger.warning(f"No content extracted for: {test_name}")
                return None
                
        except Exception as e:
            logger.error(f"Error scraping {test_name}: {e}")
            return None
    
    def scrape_all_tests(self, limit=None):
        """Scrape all medical tests"""
        tests_links = self.parse_medical_tests_page()
        
        if not tests_links:
            logger.error("No test links found. Cannot proceed.")
            return []
        
        if limit:
            tests_links = tests_links[:limit]
            logger.info(f"Limited to {limit} tests")
        
        total = len(tests_links)
        logger.info(f"Starting to scrape {total} medical tests...")
        
        for index, test in enumerate(tests_links, 1):
            logger.info(f"[{index}/{total}] Processing: {test['name']}")
            
            test_details = self.scrape_single_test(test)
            
            if test_details:
                self.tests_data.append(test_details)
                logger.info(f"  ✓ Success: {test['name']}")
            else:
                logger.warning(f"  ✗ Failed: {test['name']}")
            
            # Respectful delay
            time.sleep(1.5)
        
        logger.info(f"Successfully scraped {len(self.tests_data)}/{total} tests")
        return self.tests_data
    
    def save_to_json(self, filename='medical_tests.json'):
        """Save data to JSON in data folder"""
        output_path = os.path.join(self.output_dir, filename)
        
        # Format: list of test dicts (matches your app's expected format)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.tests_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Saved {len(self.tests_data)} tests to {output_path}")
        return output_path
    
    def print_statistics(self):
        """Print scraping statistics"""
        stats = {
            'Total Tests Scraped': len(self.tests_data),
            'Tests with Description': sum(1 for t in self.tests_data if t.get('description')),
            'Tests with Why Done': sum(1 for t in self.tests_data if t.get('why_done')),
            'Tests with Preparation': sum(1 for t in self.tests_data if t.get('how_you_prepare')),
            'Tests with Risks': sum(1 for t in self.tests_data if t.get('risks_complications')),
            'Tests with Normal Values': sum(1 for t in self.tests_data if t.get('normal_values')),
        }
        
        print("\n" + "="*60)
        print("MEDICAL TESTS SCRAPING STATISTICS")
        print("="*60)
        for key, value in stats.items():
            print(f"{key:.<40} {value}")
        print("="*60)
        
        return stats


def main():
    """Main execution"""
    scraper = FixedMedicalTestsScraper()
    
    # Scrape tests (limit=20 for testing, limit=None for all)
    scraper.scrape_all_tests(limit=None)  # Start with 20 for testing
    
    # Save to data folder
    output_file = scraper.save_to_json('medical_tests.json')
    
    # Print statistics
    scraper.print_statistics()
    
    print(f"\n✅ Output saved to: {output_file}")
    print("🚀 Restart your Streamlit app to load the new data!")


if __name__ == "__main__":
    main()