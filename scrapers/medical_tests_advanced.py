import requests
from bs4 import BeautifulSoup
import json
import time
from urllib.parse import urljoin
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('medical_tests_scraping.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class AdvancedMedicalTestsScraper:
    def __init__(self, max_workers=5):
        self.base_url = "https://medlineplus.gov/lab-tests"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        self.tests_data = []
        self.max_workers = max_workers
        self.cache_file = 'medical_tests_cache.json'
        self.failed_tests = []
    
    def load_cache(self):
        """Load previously scraped data"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cached = json.load(f)
                    logger.info(f"Loaded {len(cached)} tests from cache")
                    return cached
            except Exception as e:
                logger.warning(f"Could not load cache: {e}")
        return []
    
    def save_cache(self):
        """Save cache intermittently"""
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump(self.tests_data, f, ensure_ascii=False, indent=2)
    
    def fetch_page(self, url, retry_count=3):
        """Fetch page with retry logic"""
        for attempt in range(retry_count):
            try:
                response = requests.get(url, headers=self.headers, timeout=15)
                response.raise_for_status()
                return response.text
            except requests.exceptions.RequestException as e:
                if attempt < retry_count - 1:
                    wait_time = 2 ** attempt
                    logger.warning(f"Retry {attempt + 1} for {url} in {wait_time}s")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Failed to fetch {url} after {retry_count} retries: {e}")
                    return None
    
    def parse_medical_tests_page(self):
        """Parse the main medical tests listing page"""
        logger.info("Parsing main medical tests page...")
        html = self.fetch_page(self.base_url)
        
        if not html:
            logger.error("Could not fetch main page")
            return []
        
        soup = BeautifulSoup(html, 'html.parser')
        tests_links = []
        
        # Find all test links
        main_content = soup.find('main') or soup.find('article')
        
        if main_content:
            for link in main_content.find_all('a', href=True):
                href = link.get('href')
                test_name = link.get_text(strip=True)
                
                if href and test_name and '/lab-tests/' in href and len(test_name) > 2:
                    full_url = urljoin(self.base_url, href)
                    
                    # Filter out navigation links and duplicates
                    if full_url != self.base_url and not any(t['url'] == full_url for t in tests_links):
                        tests_links.append({
                            'name': test_name,
                            'url': full_url
                        })
        
        logger.info(f"Found {len(tests_links)} unique test links")
        return tests_links
    
    def extract_test_content(self, soup, test_name):
        """Extract structured content from test page"""
        test_data = {
            'name': test_name,
            'url': '',
            'description': '',
            'why_done': '',
            'what_happens': '',
            'risks_complications': '',
            'normal_values': '',
            'what_results_mean': '',
            'special_considerations': '',
            'scraped_at': datetime.now().isoformat()
        }
        
        try:
            # Extract main content
            main_content = soup.find('main') or soup.find('article')
            
            if not main_content:
                return None
            
            # Extract all sections with headings
            sections = {}
            current_section = None
            
            for element in main_content.find_all(['h2', 'h3', 'p', 'li', 'ul', 'ol']):
                if element.name in ['h2', 'h3']:
                    heading_text = element.get_text(strip=True).lower()
                    current_section = heading_text
                    sections[current_section] = []
                elif current_section and element.name in ['p', 'li']:
                    text = element.get_text(strip=True)
                    if text and len(text) > 10:
                        sections[current_section].append(text)
            
            # Map sections to structured fields
            for section_title, content in sections.items():
                content_text = ' '.join(content[:2])  # Take first 2 paragraphs
                
                if 'description' in section_title or 'overview' in section_title or 'summary' in section_title:
                    test_data['description'] = content_text
                elif 'why' in section_title or 'when' in section_title or 'purpose' in section_title:
                    test_data['why_done'] = content_text
                elif 'procedure' in section_title or 'happen' in section_title or 'during' in section_title:
                    test_data['what_happens'] = content_text
                elif 'risk' in section_title or 'complication' in section_title or 'side effect' in section_title:
                    test_data['risks_complications'] = content_text
                elif 'normal' in section_title or 'range' in section_title or 'value' in section_title:
                    test_data['normal_values'] = content_text
                elif 'result' in section_title or 'mean' in section_title:
                    test_data['what_results_mean'] = content_text
                elif 'consideration' in section_title or 'important' in section_title or 'note' in section_title:
                    test_data['special_considerations'] = content_text
            
            return test_data
            
        except Exception as e:
            logger.error(f"Error extracting content for {test_name}: {e}")
            return None
    
    def scrape_single_test(self, test_info):
        """Scrape a single test with error handling"""
        test_name = test_info['name']
        test_url = test_info['url']
        
        try:
            html = self.fetch_page(test_url)
            if not html:
                self.failed_tests.append({'name': test_name, 'url': test_url, 'reason': 'Failed to fetch'})
                return None
            
            soup = BeautifulSoup(html, 'html.parser')
            test_data = self.extract_test_content(soup, test_name)
            
            if test_data:
                test_data['url'] = test_url
                return test_data
            else:
                self.failed_tests.append({'name': test_name, 'url': test_url, 'reason': 'Failed to extract'})
                return None
                
        except Exception as e:
            logger.error(f"Error scraping {test_name}: {e}")
            self.failed_tests.append({'name': test_name, 'url': test_url, 'reason': str(e)})
            return None
    
    def scrape_all_tests_parallel(self, limit=None):
        """Scrape all tests using parallel processing"""
        # Get all test links
        tests_links = self.parse_medical_tests_page()
        
        if limit:
            tests_links = tests_links[:limit]
        
        total = len(tests_links)
        logger.info(f"Starting parallel scraping of {total} tests with {self.max_workers} workers...")
        
        completed = 0
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_test = {
                executor.submit(self.scrape_single_test, test): test 
                for test in tests_links
            }
            
            for future in as_completed(future_to_test):
                test_info = future_to_test[future]
                completed += 1
                
                try:
                    result = future.result()
                    if result:
                        self.tests_data.append(result)
                        logger.info(f"[{completed}/{total}] ✓ {test_info['name']}")
                    else:
                        logger.warning(f"[{completed}/{total}] ✗ {test_info['name']}")
                except Exception as e:
                    logger.error(f"[{completed}/{total}] Error with {test_info['name']}: {e}")
                
                # Save cache every 20 tests
                if completed % 20 == 0:
                    self.save_cache()
                    logger.info(f"Cache saved after {completed} tests")
        
        logger.info(f"Scraping completed. Successfully scraped: {len(self.tests_data)}/{total}")
        return self.tests_data
    
    def save_to_json(self, filename='medlineplus_medical_tests.json'):
        """Save data to JSON"""
        output = {
            'metadata': {
                'total_tests': len(self.tests_data),
                'failed_tests': len(self.failed_tests),
                'scraped_at': datetime.now().isoformat(),
                'source': 'https://medlineplus.gov/lab-tests'
            },
            'tests': self.tests_data,
            'failed': self.failed_tests
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Saved {len(self.tests_data)} tests to {filename}")
    
    def save_csv_summary(self, filename='medical_tests_summary.csv'):
        """Save summary as CSV for easy viewing"""
        import csv
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Test Name', 'URL', 'Has Description', 'Has Why Done', 'Has Risks'])
            
            for test in self.tests_data:
                writer.writerow([
                    test['name'],
                    test['url'],
                    bool(test.get('description')),
                    bool(test.get('why_done')),
                    bool(test.get('risks_complications'))
                ])
        
        logger.info(f"Saved CSV summary to {filename}")
    
    def print_statistics(self):
        """Print scraping statistics"""
        stats = {
            'Total Tests Scraped': len(self.tests_data),
            'Failed Tests': len(self.failed_tests),
            'Tests with Description': sum(1 for t in self.tests_data if t.get('description')),
            'Tests with Why Done': sum(1 for t in self.tests_data if t.get('why_done')),
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
    scraper = AdvancedMedicalTestsScraper(max_workers=5)
    
    # Load any cached data first
    cached_data = scraper.load_cache()
    scraper.tests_data = cached_data
    
    # Scrape tests
    # For testing: limit=50
    # For full scrape: limit=None (all ~350 tests)
    scraper.scrape_all_tests_parallel(limit=50)  # Start with 50
    
    # Save results
    scraper.save_to_json('medlineplus_medical_tests.json')
    scraper.save_csv_summary('medical_tests_summary.csv')
    
    # Print statistics
    scraper.print_statistics()


if __name__ == "__main__":
    main()