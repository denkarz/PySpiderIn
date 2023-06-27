import argparse
import csv
import datetime
import enum
import logging
import os
import sys
import time
import traceback

from progress.bar import Bar
from selenium.common.exceptions import NoSuchElementException, InvalidSessionIdException

import utils
from css_selectors import LinkedinSelectors
from information_messages import LinkedinErrors
from model.LinkedinJob import LinkedinJob

logging.basicConfig(format='%(asctime)-15s %(levelname)7s: %(message)4s', level=logging.INFO)
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait


class JobTypeEnum(enum.Enum):
    HYBRID = 'HYBRID'
    ON_SITE = 'ON_SITE'
    REMOTE = 'REMOTE'

    def __str__(self):
        return self.value

parser = argparse.ArgumentParser(description='CSV Linkedin parser.')
# parser.add_argument('-e', '--error-file-path', required=False, default=False, help='default error log file path')
# parser.add_argument('-f', '--file-path', required=False, default=False, help='dafault file path')
parser.add_argument('-a', '--apply-link', required=False, default=False, action=argparse.BooleanOptionalAction, help='parse with apply-link (Easy Apply not supported)')
parser.add_argument('-d', '--distance-filter', required=False, choices=[0,1,2,3,4,5], type=int, help='search distance')
parser.add_argument('-k', '--keyword', required=True, help='search keyword')
parser.add_argument('-l', '--location', required=False, default='Worldwide', help='search location')
parser.add_argument('-p', '--password', required=True, help='user password')
parser.add_argument('-t', '--job-type-filter',choices=list(JobTypeEnum), type=JobTypeEnum, required=False, help='add a job type filter', nargs="*")
parser.add_argument('-u', '--username', required=True, help='user login')
# указания путей файлов результата и логов + корректная работа аплай_линк
args = parser.parse_args()

LINKEDIN_COM = 'https://www.linkedin.com'
USERNAME = args.username
PASSWORD = args.password
KEYWORD = args.keyword
LOCATION = args.location
CSV_FILE_PATH = os.path.dirname(sys.argv[0])
CSV_FILE_NAME = KEYWORD.replace(",", "").replace(" ", "_") + '_' + LOCATION.replace(",", "").replace(" ", "_") + '.csv'
ERROR_FILE_NAME = 'error.log'
FULL_CSV_FILE_NAME = os.path.abspath(os.path.join(CSV_FILE_PATH, CSV_FILE_NAME))
FULL_ERROR_FILE_NAME = os.path.abspath(os.path.join(CSV_FILE_PATH, ERROR_FILE_NAME))
SAVE_APPLY_LINK = args.apply_link
JOB_TYPE_FILTER = args.job_type_filter
JOB_DISTANCE_FILTER = args.distance_filter

CSV_HEADER = ['job_name', 'company_name', 'company_size', 'company_domain', 'company_link', 'job_work_type',
              'job_description', 'job_apply_link', 'job_location']
DELAY = 180


class Maintains:
    def __init__(self, driver, error_log_file):
        self.driver = driver
        self.writer = None
        self.error_log_file = error_log_file
        self.next_page = 2
        self.next_page_idx = 1
        self.flag = False


def auth(driver):
    driver.get(LINKEDIN_COM)
    username = driver.find_element(By.ID, LinkedinSelectors.USERNAME_INPUT_ID)
    username.send_keys('%s' % USERNAME)
    password = driver.find_element(By.ID, LinkedinSelectors.PASSWORD_INPUT_ID)
    password.send_keys('%s' % PASSWORD)
    password.send_keys(Keys.ENTER)


def wait_page_loaded(driver):
    WebDriverWait(driver, DELAY).until(EC.presence_of_element_located((By.ID, LinkedinSelectors.LINKEDIN_LOGO_ID)))


def wait_apply_button(driver):
    WebDriverWait(driver, DELAY).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, LinkedinSelectors.APPLY_JOB_BUTTON_SELECTOR)))


def instant_delay():
    time.sleep(2)


def build_error_message(text, e, log_file):
    logging.debug("{0}: {1}\n".format(text, str(e)))
    log_file.write("{0}: {1}\n".format(text, str(e)))
    log_file.write(traceback.format_exc())


def search(maintains):
    driver = maintains.driver
    wait_page_loaded(driver)
    driver.get('%s/jobs/search/' % LINKEDIN_COM)
    wait_page_loaded(driver)
    instant_delay()
    location = driver.find_elements_by_css_selector(LinkedinSelectors.SEARCH_LOCATION_INPUT_SELECTOR)
    location[0].clear()
    location[0].send_keys(LOCATION)
    location[0].send_keys(Keys.ENTER)
    position = driver.find_element_by_css_selector(LinkedinSelectors.SEARCH_KEYWORD_INPUT_SELECTOR)
    position.send_keys(KEYWORD)
    position.send_keys(Keys.ENTER)
    process_filter(driver)
    process_search_request(maintains)


def process_filter(driver):
    filters = driver.find_element_by_css_selector(LinkedinSelectors.SEARCH_ALL_FILTER_BUTTON_SELECTOR)
    filters.click()
    instant_delay()

    if JOB_TYPE_FILTER is not None:
        job_work_type_filter = driver.find_elements_by_css_selector(LinkedinSelectors.SEARCH_FILTER_ALL_SECTORS_SELECTOR)[5]
        driver.execute_script('arguments[0].scrollIntoView();', job_work_type_filter)
        work_type_checkbox = job_work_type_filter.find_elements_by_css_selector(LinkedinSelectors.SEARCH_FILTER_SECTOR_ALL_CHECKBOXES_SELECTOR)
        if JobTypeEnum.ON_SITE in JOB_TYPE_FILTER:
            work_type_checkbox[0].find_element_by_css_selector(LinkedinSelectors.SEARCH_FILTER_SECTOR_CHECKBOX_SELECTOR).click()
        if JobTypeEnum.REMOTE in JOB_TYPE_FILTER:
            work_type_checkbox[1].find_element_by_css_selector(LinkedinSelectors.SEARCH_FILTER_SECTOR_CHECKBOX_SELECTOR).click()
        if JobTypeEnum.HYBRID in JOB_TYPE_FILTER:
            work_type_checkbox[2].find_element_by_css_selector(LinkedinSelectors.SEARCH_FILTER_SECTOR_CHECKBOX_SELECTOR).click()
    if JOB_DISTANCE_FILTER is not None:
        slider = driver.find_element_by_css_selector(LinkedinSelectors.SEARCH_FILTER_DISTANCE_SLIDER_SELECTOR)
        driver.execute_script('arguments[0].scrollIntoView();', slider)
        for i in range(6):
             slider.send_keys(Keys.LEFT)
        for i in range(JOB_DISTANCE_FILTER):
            slider.send_keys(Keys.RIGHT)
    driver.find_element_by_css_selector(LinkedinSelectors.SEARCH_APPLY_FILTER_BUTTON_SELECTOR).click()
    instant_delay()


def process_search_request(maintains):
    driver = maintains.driver
    wait_page_loaded(driver)
    instant_delay()
    page_buttons = driver.find_elements_by_css_selector(LinkedinSelectors.PAGINATION_BAR_SELECTOR)
    last_page = int(page_buttons[len(page_buttons) - 1].text)
    with open(FULL_CSV_FILE_NAME, 'w', newline='') as file:
        writer = csv.writer(file)
        maintains.writer = writer
        writer.writerow(CSV_HEADER)
        while maintains.next_page <= last_page:
            process_page(maintains, last_page)


def process_page(maintains, stop):
    logging.debug('page_index: %s, process_page: %s', maintains.next_page_idx, maintains.next_page)
    driver = maintains.driver
    cards = driver.find_elements_by_css_selector(LinkedinSelectors.CARDS_SELECTOR)
    process_cards(maintains, len(cards))
    fetch_next_page(maintains, stop)


def process_cards(maintains, page_size):
    driver = maintains.driver
    log_file = maintains.error_log_file
    with Bar('Process page ' + str(maintains.next_page), max=page_size) as bar:
        for idx in range(page_size):
            card = driver.find_elements_by_css_selector(LinkedinSelectors.CARDS_SELECTOR)[idx]
            driver.execute_script('arguments[0].scrollIntoView();', card)
            try:
                card_title = card.find_element_by_css_selector(LinkedinSelectors.CARD_TITLE_SELECTOR)
                card_title.click()
                process_job(maintains)
            except Exception as e:
                error_text = LinkedinErrors.SKIP_NON_JOB_CARD_INFO.format(card.text, card.get_attribute('class'))
                build_error_message(error_text, e, log_file)
            finally:
                bar.next()


def process_job(maintains):
    driver = maintains.driver
    log_file = maintains.error_log_file
    wait_apply_button(maintains.driver)
    selector = driver.find_element_by_css_selector(LinkedinSelectors.CARD_DETAILS_SELECTOR)
    job_name = None
    company_name = None
    company_link = None
    job_location = None
    job_work_type = None
    company_size = None
    job_description = None
    job_apply_link = None
    company_domain = None
    try:
        job_name = selector.find_element_by_css_selector(LinkedinSelectors.CARD_DETAILS_JOB_TITLE_SELECTOR).text
    except NoSuchElementException as e:
        build_error_message(LinkedinErrors.JOB_NAME_NOT_FOUND_ERR, e, log_file)
    try:
        css_selector = selector.find_element_by_css_selector(LinkedinSelectors.CARD_DETAILS_COMPANY_NAME_SELECTOR)
        company_name = css_selector.text
        company_link = css_selector.get_attribute('href')
    except NoSuchElementException as e:
        build_error_message(LinkedinErrors.COMPANY_NAME_NOT_FOUND_ERR, e, log_file)
    if SAVE_APPLY_LINK:
        try:
            job_apply_link_selector = selector.find_element_by_css_selector(LinkedinSelectors.APPLY_JOB_BUTTON_SELECTOR)
            if job_apply_link_selector.text != 'Easy Apply':
                job_apply_link_selector.click()
                driver.switch_to.window(driver.window_handles[-1])
                job_apply_link = driver.current_url
            else:
                job_apply_link = 'Easy Apply'
        except NoSuchElementException as e:
            build_error_message(LinkedinErrors.JOB_APPLY_LINK_NOT_FOUND_ERR, e, log_file)
        except InvalidSessionIdException as e:
            build_error_message(LinkedinErrors.INVALID_SESSION_ID_ERR, e, log_file)
        finally:
            for x in range(1, len(driver.window_handles)):
                driver.switch_to.window(driver.window_handles[x])
                driver.close()
            driver.switch_to.window(driver.window_handles[0])

    try:
        job_location = selector.find_element_by_css_selector(LinkedinSelectors.CARD_DETAILS_JOB_LOCATION_SELECTOR).text
    except NoSuchElementException as e:
        build_error_message(LinkedinErrors.JOB_LOCATION_NOT_FOUND_ERR, e, log_file)
    try:
        job_work_type = selector.find_element_by_css_selector(
            LinkedinSelectors.CARD_DETAILS_JOB_WORK_TYPE_SELECTOR).text
    except NoSuchElementException as e:
        build_error_message(LinkedinErrors.JOB_WORK_TYPE_NOT_FOUND_ERR, e, log_file)
    try:
        company_size_selector = selector.find_elements_by_css_selector(LinkedinSelectors.CARD_DETAILS_JOB_SIZE_SELECTOR)
        if company_size_selector is not None and len(company_size_selector) > 1:
            company_size_selector_text = company_size_selector[1].text
            company_size = company_size_selector_text.split('·')[0].strip()
            company_domain = company_size_selector_text.split('·')[1].strip()
    except NoSuchElementException as e:
        build_error_message(LinkedinErrors.COMPANY_SIZE_NOT_FOUND_ERR, e, log_file)
    try:
        job_description = selector.find_element_by_css_selector(
            LinkedinSelectors.CARD_DETAILS_JOB_DESCRIPTION_SELECTOR).text.strip()
    except NoSuchElementException as e:
        build_error_message(LinkedinErrors.JOB_DESCRIPTION_FOUND_ERR, e, log_file)
    current_job = LinkedinJob(job_name=job_name, company_name=company_name,
                              company_link=company_link, company_size=company_size,
                              job_location=job_location,
                              job_apply_link=job_apply_link, job_description=job_description,
                              job_work_type=job_work_type, company_domain=company_domain)
    current_job.print_csv(maintains)


def fetch_next_page(maintains, stop):
    driver = maintains.driver
    buttons = driver.find_elements_by_css_selector(LinkedinSelectors.PAGINATION_PAGE_BUTTON_SELECTOR)
    if maintains.next_page > 9 and maintains.flag is False:
        maintains.next_page_idx = 6
    if maintains.next_page > stop - 7 and maintains.flag is False:
        maintains.next_page_idx = 2
        maintains.flag = True
    buttons[maintains.next_page_idx].click()
    maintains.next_page = maintains.next_page + 1
    maintains.next_page_idx = maintains.next_page_idx + 1


def info():
    logging.info('USERNAME: %s', USERNAME)
    logging.info('PASSWORD: %s', utils.secret(PASSWORD))
    logging.info('KEYWORDS: %s', KEYWORD)
    logging.info('LOCATION: %s', LOCATION)
    logging.info('JOB_TYPE_FILTER: %s', JOB_TYPE_FILTER)
    logging.info('JOB_DISTANCE_FILTER: %s', JOB_DISTANCE_FILTER)
    logging.info('SAVE_APPLY_LINK: %s', SAVE_APPLY_LINK)
    logging.debug('DELAY: %s', DELAY)
    logging.info('FULL_CSV_FILE_NAME: %s', FULL_CSV_FILE_NAME)
    logging.info('FULL_ERROR_FILE_NAME: %s', FULL_ERROR_FILE_NAME)
    logging.debug('CSV_HEADER: %s', CSV_HEADER)


def main():
    log_file = open(FULL_ERROR_FILE_NAME, "w")
    start_time = time.time()
    try:
        maintains = Maintains(webdriver.Chrome(options=Options()), log_file)
        info()
        auth(maintains.driver)
        logging.info("Linkedin parser start")
        search(maintains)
    except Exception as e:
        build_error_message(LinkedinErrors.COMMON_ERR, e, log_file)
    finally:
        logging.info("Linkedin parser stop")
        print("--- %s ---" % (str(datetime.timedelta(seconds=time.time() - start_time))))
        sys.exit()


if __name__ == '__main__':
    main()
