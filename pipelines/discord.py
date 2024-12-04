import time
from selenium.webdriver.common.by import By
import os

def login(browser, DISCORD_USER, DISCORD_PASS):
    """Login to Discord with session handling"""
    try:
        # First try to load existing session
        browser.navigate("https://discord.com/channels/@me")
        time.sleep(3)
        
        x, y = browser.locate_element_by_text("Continue In Browser", element_type="button")
        if x and y:
            browser.click_at(x, y)
            time.sleep(3)
        """
        # Enter email/username
        x, y = browser.locate_element_by_text("Email", element_type="input")
        if x and y:
            browser.click_and_type(x, y, DISCORD_USER)
            time.sleep(2)

        # Enter password
        x, y = browser.locate_element_by_text("Password", element_type="input")
        if x and y:
            browser.click_and_type(x, y, DISCORD_PASS)
            time.sleep(2)

        # Press Enter key
        browser.press_key("enter")
        time.sleep(5)"""
        # Save cookies after successful login
        browser.save_cookies()
        return True
        
    except Exception as e:
        print(f"Login error: {e}")
        return False



# Add this new function after the locate_element function
def click_join_voice(browser):
    """Click the Join Voice button using various selectors."""
    try:
        # Try multiple selectors to find the Join Voice button
        selectors = [
            "//button[contains(@class, 'joinButton') and .//div[contains(text(), 'Join Voice')]]",
            "//button[contains(@class, 'colorGreen') and .//div[contains(text(), 'Join Voice')]]",
            "//button[contains(@class, 'button_dd4f85') and .//div[contains(text(), 'Join Voice')]]"
        ]
        
        for selector in selectors:
            try:
                element = browser.driver.find_element(By.XPATH, selector)
                location = element.location
                size = element.size
                center_x = location['x'] + (size['width'] / 2)
                center_y = location['y'] + (size['height'] / 2)
                print(f"Found Join Voice button at ({center_x}, {center_y})")
                browser.click_at(center_x, center_y)
                time.sleep(2)  # Wait for voice channel to connect
                return True
            except:
                continue
                
        print("Could not find Join Voice button with standard selectors")
        return False
        
    except Exception as e:
        print(f"Error clicking Join Voice button: {e}")
        return False
