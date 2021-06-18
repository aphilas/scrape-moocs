from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import pytimeparse
import time
import csv

driver = webdriver.Firefox()
# driver = None

price_selector = '.sidebar-container--purchase-section--17KRp > div:nth-child(1) > div:nth-child(1) > div:nth-child(1) > div:nth-child(2) > div:nth-child(1) > div:nth-child(1) > div:nth-child(1) > span:nth-child(2) > span:nth-child(1)'
with_discount_selector = '.sidebar-container--purchase-section--17KRp > div:nth-child(1) > div:nth-child(1) > div:nth-child(1) > div:nth-child(2) > div:nth-child(1) > div:nth-child(1) > div:nth-child(2) > div:nth-child(1) > span:nth-child(2) > s:nth-child(1) > span:nth-child(1)'
length_selector = '[data-purpose="video-content-length"]'
# title_selector = 'h1.udlite-heading-xl'

def wait_for_element(selector, timeout=5):
    try:
        return WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
        )
    except TimeoutException:
        print('Timed out') 

def find_element(selector):
    try:
        return driver.find_element_by_css_selector(selector)
    except NoSuchElementException:
        print('Element not found')

def text(element):
    if element:
        return element.text
    else:
        return ''

# hour, hours, minute, minutes -> seconds
def duration_to_hours(string):
    result = pytimeparse.parse(string) # returns None if parsing fails
    return round(result/ 3600, 2) if string and result else ''

def get_courses(urls):
    courses = []

    for id, url in urls:
        # cat1, cat2, cat3, title, caption, rating, num_ratings, subscribers, instructor, organization, updated, language, cc, price, without discount, discount_duration, content_lenght, articles, practice_tests?, [description], num_lectures
        course = {
            'id': id,
            'url': url,
        }

        try:
            driver.get(url) 

            course['price'] = text(wait_for_element(price_selector)).lstrip('$')
            course['with_discount'] = text(find_element(with_discount_selector)).lstrip('$') # would have loaded if with discount is ready
            
            duration_string = text(find_element(length_selector)).rstrip(' on-demand video')
            course['content_length'] = duration_to_hours(duration_string)

            if course['price'] == '' or course['with_discount'] == '':
                print(url)

            courses.append(course)
        except Exception as e:
            print(e)
            # raise e
    
    driver.close()
    return courses

def save_courses(courses, output_file):
    if len(courses) > 0:
        field_names = courses[0].keys()
    else:
        print('Courses is empty')
        return

    with open(output_file, 'a') as fd:
        writer = csv.DictWriter(fd, fieldnames=field_names)
        writer.writeheader()
        writer.writerows(courses)

def get_urls(file_link):
    with open(file_link) as fd:
        reader = csv.DictReader(fd)
        return [(index, course['Link']) for index, course in enumerate(reader)]

courses_file = './data/udemy.csv'
output_file = './out/udemy-prices-v2.csv'

save_courses(get_courses(get_urls(courses_file)), output_file)
