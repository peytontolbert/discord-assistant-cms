import time
from selenium.webdriver.common.by import By

def login(browser, SPOTIFY_USER, SPOTIFY_PASS):
    # Navigate to Spotify login
    browser.navigate("https://accounts.spotify.com/login")
    time.sleep(5)  # Wait for initial page load

    # Enter email/username
    x, y = browser.locate_element_by_text("Email address or username", element_type="input")
    if x and y:
        browser.click_and_type(x, y, SPOTIFY_USER)
        time.sleep(3)

    # Enter password
    x, y = browser.locate_element_by_text("Password", element_type="input")
    if x and y:
        browser.click_and_type(x, y, SPOTIFY_PASS)
        time.sleep(3)

    # Click the login button
    x, y = browser.locate_element_by_text("Log In", element_type="button")
    if x and y:
        browser.click_at(x, y)
        time.sleep(3)
    
    return True
