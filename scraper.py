from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
import dotenv
import pytimeparse
import csv
import re
import os

dotenv.load_dotenv('./.env')
TIMEOUT = 5

# TODO: append to CSV line by line, in case of error...

def find(seq, fn=None, default=None):
    '''Returns first element in seq for which fn(element) is true else returns default'''
    return next(filter(fn, seq), default)

def duration_to_hours(string):
    '''Converts human readable durations such as 2 days to hours
    Returns float or empty string'''
    result = pytimeparse.parse(string) # returns None or seconds
    return round(result/ 3600, 2) if string and result else ''

class Scraper:
    def __init__(self, with_profile=False):
        profile_dir = os.getenv('PROFILE_DIR', '')

        try:
            if with_profile and profile_dir:
                profile = webdriver.FirefoxProfile(profile_dir)
                self.driver = webdriver.Firefox(profile)
            else:
                self.driver = webdriver.Firefox()
        except Exception as e:
            print(e)

    def find_element(self, selector):
        try:
            return self.driver.find_element_by_css_selector(selector)
        except NoSuchElementException:
            print(f'Element not found: {selector}')

    def wait_for_element(self, selector, timeout=TIMEOUT):
        try:
            return WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
        except TimeoutException:
            print(f'Timed out: {selector}') 

    def wait_until_clickable(self, selector, timeout=TIMEOUT):
        try:
            return WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
            )
        except TimeoutException:
            print(f'Timed out: {selector}')

    def find_visible_elements(self, selector):
        return filter(lambda element: element.is_displayed(), self.driver.find_elements_by_css_selector(selector))
    
    def text(self, element):
        if element:
            return element.text
        else:
            return ''

class ScrapeCoursera(Scraper):
    selectors = {
        'course_details': '.ProductGlance > div > div:nth-child(2) > div:first-child',
        'enroll_button': '[data-e2e="enroll-button"]',
        'price': '.rc-ReactPriceDisplay > span:first-child',
        'next_button': '[data-track-component="course_enroll_s12n_selection_button"]',

        # modal options after clicking enroll button
        'free_trial': '.rc-SubscriptionVPropFreeTrial',
        'enroll_modal': '.rc-CourseEnrollS12nSelectionModal',
        'enroll_choice': '.enrollmentChoiceContainer',
    }

    def __init__(self):
        super().__init__(with_profile=True)

    def generate_courses(self, urls):
        courses = []
        
        for id, url in urls:
            course = self.scrape_details(url)
            course['id'] = id
            courses.append(course)

        self.driver.quit()

        return courses

    def scrape_details(self, url):
        course = {
            'url': url,
        }

        self.driver.get(url)

        # ordered
        duration = self.find_duration(self.find_visible_elements(self.selectors['course_details']))
        price = self.scrape_price()

        course['price'] = price
        course['duration'] = duration

        return course

    def find_duration(self, detail_elements):
        duration_str = find(map(lambda el: el.text, detail_elements), lambda txt: txt.startswith('Approx'))
        pattern = r'Approx(?:imately)?\.? (.+) to complete'
        match = re.search(pattern, duration_str)
        return match.group(1) if match else ''

    # Avoids StaleElementReferenceException
    def read_price(self, timeout=TIMEOUT):
        try:
            price_el = WebDriverWait(
                self.driver, 
                timeout, 
                ignored_exceptions=[StaleElementReferenceException]
            ).until(
                EC.text_to_be_present_in_element((By.CSS_SELECTOR, self.selectors['price']), '$')
            )

            return self.text(self.find_element(self.selectors['price'])).lstrip('$') if price_el else ''
        except TimeoutException:
            print(f'Timed out: {self.selectors["price"]}')
            return ''

    def scrape_price(self):
        enroll_button = self.wait_for_element(self.selectors['enroll_button'])

        if enroll_button:
            enroll_button.click()
        else:
            print('Enroll button not found')
            return ''

        # 'filter' dict
        modals = {key:value for (key, value) in self.selectors.items() if key in ('free_trial', 'enroll_modal', 'enroll_choice')}

        modals_selector = ','.join(modals.values())
        modal = self.wait_for_element(modals_selector)

        if not modal:
            return ''

        modal_class = modal.get_attribute('class')

        # 0 - key, 1 - value
        matching_modal = find(modals.items(), lambda modal_spec: modal_spec[1].lstrip('.') in modal_class)[0]

        if matching_modal == 'free_trial':
            return self.read_price()
        elif matching_modal == 'enroll_modal':    
            next_button = self.wait_until_clickable(self.selectors['next_button'])

            if not next_button:
                return ''
            next_button.click()

            return self.read_price()
        elif matching_modal == 'enroll_choice':
            # course free to audit - maybe record that?
            return self.read_price()
        else:
            print("Couldn't match a modal")
            return ''

class ScrapeUdemy(Scraper):
    # TODO - improve selectors, fetch other attrs
    selectors = {
        'price': '.sidebar-container--purchase-section--17KRp > div:nth-child(1) > div:nth-child(1) > div:nth-child(1) > div:nth-child(2) > div:nth-child(1) > div:nth-child(1) > div:nth-child(1) > span:nth-child(2) > span:nth-child(1)',
        'with_discount': '.sidebar-container--purchase-section--17KRp > div:nth-child(1) > div:nth-child(1) > div:nth-child(1) > div:nth-child(2) > div:nth-child(1) > div:nth-child(1) > div:nth-child(2) > div:nth-child(1) > span:nth-child(2) > s:nth-child(1) > span:nth-child(1)',
        'length': '[data-purpose="video-content-length"]',
        'title': 'h1.udlite-heading-xl',
    }

    def __init__(self):
        # start driver
        super().__init__()

    def get_courses(self, urls):
        courses = []

        for id, url in urls:
            course = {
                'id': id,
                'url': url,
            }

            try:
                self.driver.get(url) 

                course['price'] = self.text(self.wait_for_element(self.selectors['price'])).lstrip('$')
                course['with_discount'] = self.text(self.find_element(self.selectors['with_discount'])).lstrip('$') # would have loaded if with discount is ready
                duration_string = self.text(self.find_element(self.selectors['length'])).rstrip(' on-demand video')
                course['content_length'] = duration_to_hours(duration_string)

                if course['price'] == '' or course['with_discount'] == '':
                    print(url)

                courses.append(course)  
            except Exception as e:
                print(e)
        
        self.driver.close()
        return courses

def save_courses(courses, output_file, append=False):
    '''Save sequence of course dicts as csv'''
    if len(courses) > 0:
        field_names = courses[0].keys()
    else:
        print('courses is empty')
        return

    mode = 'a' if append else 'w'

    with open(output_file, mode) as fd:
        writer = csv.DictWriter(fd, fieldnames=field_names)
        writer.writeheader()
        writer.writerows(courses)

def extract_col(file_link, col_name):
    '''Generate (index, value) for every row in file_link csv'''
    with open(file_link) as fd:
        reader = csv.DictReader(fd)
        return [(index, course[col_name]) for index, course in enumerate(reader)]


udemy_input = './data/udemy.csv'
udemy_output = './out/udemy-prices-v2.csv'
# udemy_courses = ScrapeUdemy().get_courses(extract_col(udemy_input, 'Link'))
# save_courses(udemy_courses, udemy_output)

coursera_input = './data/coursera.csv'
coursera_output = './out/coursera.csv'
coursera_urls = extract_col(coursera_input, 'Link')
coursera_courses = ScrapeCoursera().generate_courses(coursera_urls)
save_courses(coursera_courses, coursera_output)
