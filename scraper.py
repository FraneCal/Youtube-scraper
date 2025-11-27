import os
import time
import csv
import logging
from logging.handlers import RotatingFileHandler
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

# Setup rotating logs
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
log_handler = RotatingFileHandler("scraper.log", maxBytes=5*1024*1024, backupCount=5)
log_handler.setFormatter(log_formatter)
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(log_handler)

# Make sure screenshot folder exists
if not os.path.exists("screenshots"):
    os.makedirs("screenshots")

def save_screenshot(driver, name="error"):
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    filename = f"screenshots/{name}_{timestamp}.png"
    driver.save_screenshot(filename)
    logger.info(f"Screenshot saved: {filename}")

def scrape_youtube_links(url):
    opts = Options()
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--start-maximized")
    opts.add_argument("--headless")
    driver = webdriver.Chrome(options=opts)
    driver.get(url)

    # Accept cookies only once
    try:
        accept_cookies = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, '//*[@id="content"]/div[2]/div[6]/div[1]/ytd-button-renderer[2]/yt-button-shape/button'))
        )
        accept_cookies.click()
        logger.info("Clicked accept cookies button")
        WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'a#video-title'))
        )
    except TimeoutException:
        logger.info("No accept cookies button found or videos already loaded")

    # Scroll to load all videos
    last_count = 0
    scroll_pause = 2
    while True:
        driver.execute_script("window.scrollTo(0, document.documentElement.scrollHeight);")
        time.sleep(scroll_pause)
        video_links = driver.find_elements(By.CSS_SELECTOR, 'a#video-title')
        channel_links = driver.find_elements(By.CSS_SELECTOR, "a.yt-simple-endpoint.yt-formatted-string")
        current_count = len(video_links)
        if current_count == last_count:
            break
        last_count = current_count

    # Extract URLs
    video_urls, channel_urls = [], []
    for video_link, channel_link in zip(video_links, channel_links):
        video_href = video_link.get_attribute("href")
        channel_href = channel_link.get_attribute("href")
        if video_href:
            video_urls.append(video_href)
            channel_urls.append(channel_href)

    logger.info(f"Total video results: {len(video_urls)}")
    logger.info(f"Total channel results: {len(channel_urls)}")

    driver.quit()
    # Return list of tuples (channel_url, video_url)
    return list(zip(channel_urls, video_urls))

def scrape_channel_details(channel_video_pairs):
    opts = Options()
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--start-maximized")
    # opts.add_argument("--headless")
    driver = webdriver.Chrome(options=opts)

    results = []
    accept_cookies_done = False

    # Group videos by channel
    channel_dict = {}
    for channel_url, video_url in channel_video_pairs:
        channel_dict.setdefault(channel_url, []).append(video_url)

    for channel_url, videos in channel_dict.items():
        try:
            driver.get(channel_url)
            time.sleep(1)
            # Accept cookies only once
            if not accept_cookies_done:
                try:
                    accept_cookies = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, '//*[@id="yDmH0d"]/c-wiz/div/div/div/div[2]/div[1]/div[3]/div[1]/form[2]/div/div/button'))
                    )
                    accept_cookies.click()
                    accept_cookies_done = True
                    logger.info("Clicked accept cookies button")
                except TimeoutException:
                    logger.info("No accept cookies button found.")

            # --------------------- Sign in to Gmail --------------------- #
            try:
                sign_in_button = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH,
                                                '//*[@id="buttons"]/ytd-button-renderer/yt-button-shape/a')))
                sign_in_button.click()
                logger.info("Clicked sign in button")
            except TimeoutException:
                logger.info("No sign in button found.")

            email_field = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="identifierId"]')))
            email_field.click()
            email_field.send_keys("franecalusic94@gmail.com")

            next_button = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="identifierNext"]/div/button')))
            next_button.click()

            password_field = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="password"]/div[1]/div/div[1]/input')))
            password_field.click()
            password_field.send_keys("ZekoslavMrkvicaInes")

            next_button_2 = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="passwordNext"]/div/button')))
            next_button_2.click()

            # --------------------- Expand description if available --------------------- #
            try:
                expand_button = WebDriverWait(driver, 15).until(
                    EC.element_to_be_clickable((By.XPATH,'//*[@id="page-header"]/yt-page-header-renderer/yt-page-header-view-model/div/div[1]/div/yt-description-preview-view-model/truncated-text/button'))
                )
                expand_button.click()
            except TimeoutException:
                logger.info(f"No expand button for {channel_url}")

            # --------------------- Country --------------------- #
            try:
                country_element = WebDriverWait(driver, 5).until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR,'tr.description-item:has(yt-icon[icon="privacy_public"]) td:nth-of-type(2)'))
                )
                country = country_element.text
            except TimeoutException:
                logger.warning(f"Country not found for {channel_url}")
                country = "N/A"

            # --------------------- Joined youtube since --------------------- #
            try:
                joined_youtube_element = WebDriverWait(driver, 5).until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR,
                                                      'tr.description-item:has(yt-icon[icon="info_outline"]) td:nth-of-type(2)'))
                )
                joined_youtube = joined_youtube_element.text
            except TimeoutException:
                logger.warning(f"Country not found for {channel_url}")
                joined_youtube = "N/A"

            # --------------------- No of subscribers ---------------------#
            try:
                subscribers_element = WebDriverWait(driver, 5).until(
                    EC.visibility_of_element_located(
                        (By.CSS_SELECTOR,
                         'tr.description-item:has(yt-icon[icon="person_radar"]) td:nth-of-type(2)'))
                )
                subscribers = subscribers_element.text
            except TimeoutException:
                logger.warning(f"Country not found for {channel_url}")
                subscribers = "N/A"

            # --------------------- No of videos --------------------- #
            try:
                videos_element = WebDriverWait(driver, 5).until(
                    EC.visibility_of_element_located(
                        (By.CSS_SELECTOR,
                         'tr.description-item:has(yt-icon[icon="my_videos"]) td:nth-of-type(2)'))
                )
                number_of_videos = videos_element.text
            except TimeoutException:
                logger.warning(f"Country not found for {channel_url}")
                number_of_videos = "N/A"

            # --------------------- No of views --------------------- #
            try:
                views_element = WebDriverWait(driver, 5).until(
                    EC.visibility_of_element_located(
                        (By.CSS_SELECTOR,
                         'tr.description-item:has(yt-icon[icon="trending_up"]) td:nth-of-type(2)'))
                )
                views = views_element.text
            except TimeoutException:
                logger.warning(f"Country not found for {channel_url}")
                views = "N/A"

            # --------------------- Email extraction --------------------- #
            try:
                view_email_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH,
                                                '//*[@id="view-email-button-container"]/yt-button-view-model/button-view-model/button'))
                )
                view_email_button.click()
                logger.info("Clicked view email button")
            except TimeoutException:
                logger.info("No view email button found")

            # Captcha solving logic goes here

            time.sleep(500)

            results.append((channel_url, country, joined_youtube, subscribers, number_of_videos, views, videos))
            logger.info(f"Scraped {channel_url} -> {country} -> {joined_youtube} -> {subscribers} -> {number_of_videos} -> {views}, {len(videos)} videos")


        except WebDriverException as e:
            logger.error(f"Error scraping {channel_url}: {e}")
            save_screenshot(driver, "channel_error")

    driver.quit()
    return results

def save_to_csv(filename, data):
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["channel_url", "country", "joined youtube since", "subscribers", "number_of_videos", "views", "video_urls"])
        for channel, country, joined_youtube, subscribers, number_of_videos, views, videos in data:
            writer.writerow([channel, country, joined_youtube, subscribers, number_of_videos, views] + videos)
    logger.info(f"Saved data to {filename}")

if __name__ == "__main__":
    url = 'https://www.youtube.com/results?search_query=azure&sp=EgQIARgC'
    channel_video_pairs = scrape_youtube_links(url)
    results = scrape_channel_details(channel_video_pairs)
    save_to_csv("channels.csv", results)
