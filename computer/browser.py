from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
import time
from PIL import Image, ImageDraw, ImageFont
import os
import json
import pickle

class BrowserController:
    def __init__(self, window_width=800, window_height=600, audio_output_device=None):
        # Configure Edge WebDriver
        edge_options = Options()
        edge_options.add_argument(f"--window-size={window_width},{window_height}")
        
        # Add user data directory to persist session
        user_data_dir = os.path.abspath("browser_data")
        edge_options.add_argument(f"user-data-dir={user_data_dir}")
        
        # Configure audio preferences
        edge_options.add_argument("--autoplay-policy=no-user-gesture-required")
        edge_options.add_argument("--use-fake-ui-for-media-stream")
        
        # Set up preferences for audio devices with echo cancellation
        prefs = {
            # Enable microphone with echo cancellation
            "profile.default_content_setting_values.media_stream_mic": 1,
            "profile.default_content_settings.media_stream_mic": 1,
            
            # Enable audio output with echo cancellation
            "profile.default_content_setting_values.media_stream_sound": 1,
            "profile.default_content_settings.sound": 1,
            "profile.managed_default_content_settings.sound": 1,
            
            # Enable echo cancellation and noise suppression
            "media.navigator.audio.force_noecho": True,
            "media.navigator.audio.force_noise_suppression": True,
            
            # Disable device selection prompt
            "profile.default_content_setting_values.media_stream_camera": 1,
            
            # Additional audio settings
            "managed_default_content_settings.media_stream_mic": 1,
            "managed_default_content_settings.media_stream_sound": 1
        }
        
        edge_options.add_experimental_option("prefs", prefs)
        
        # Add additional Edge-specific arguments for audio
        edge_options.add_argument("--disable-features=PreloadMediaEngagementData,AutoplayIgnoreWebAudio,MediaEngagementBypassAutoplayPolicies")
        edge_options.add_argument("--enable-features=WebRtcHideLocalIpsWithMdns,WebRtcAudioDsp")
        
        self.driver = webdriver.Edge(options=edge_options)
        time.sleep(2)  # Wait for browser to initialize
        
        # Configure viewport dimensions
        self.viewport_width = self.driver.execute_script("return window.innerWidth")
        self.viewport_height = self.driver.execute_script("return window.innerHeight")
        
        # Adjust window size
        width_diff = window_width - self.viewport_width
        height_diff = window_height - self.viewport_height
        self.driver.set_window_size(window_width + width_diff, window_height + height_diff)
        
        self.screenshot_width = 1008    
        self.screenshot_height = 1008
        
        self.actions = ActionChains(self.driver)
        self.last_mouse_position = None
        
        print(f"Initialized browser with viewport dimensions: {self.viewport_width}x{self.viewport_height}")

    def navigate(self, url):
        """Navigate to a specified URL."""
        self.driver.get(url)
        print(f"Navigated to {url}")
        time.sleep(2)  # Wait for the page to load

    def locate_element_by_text(self, text, element_type="link"):
        """
        Locate an element by text and return its center coordinates.
        
        Args:
            text (str): Text to search for
            element_type (str): Type of element to look for ("link", "input", "button")
        """
        try:
            element = None
            if element_type == "link":
                element = self.driver.find_element(By.LINK_TEXT, text)
            elif element_type == "input":
                # Try different strategies for input fields
                selectors = [
                    f"//input[@placeholder='{text}']",
                    f"//input[@name='{text}']",
                    f"//input[@type='{text}']",
                    f"//label[contains(text(), '{text}')]//following::input[1]",
                    f"//div[contains(text(), '{text}')]//following::input[1]"
                ]
                for selector in selectors:
                    try:
                        element = self.driver.find_element(By.XPATH, selector)
                        break
                    except:
                        continue
            elif element_type == "button":
                # Try different strategies for buttons
                selectors = [
                    f"//button[contains(text(), '{text}')]",
                    f"//button[@type='{text}']",
                    f"//div[contains(@class, 'button') and contains(text(), '{text}')]",
                    f"//*[contains(@class, 'button') and contains(text(), '{text}')]"
                ]
                for selector in selectors:
                    try:
                        element = self.driver.find_element(By.XPATH, selector)
                        break
                    except:
                        continue

            if element:
                location = element.location
                size = element.size
                center_x = location['x'] + (size['width'] / 2)
                center_y = location['y'] + (size['height'] / 2)
                print(f"Located {element_type} element '{text}' at ({center_x}, {center_y})")
                return center_x, center_y
            else:
                print(f"Could not locate {element_type} element with text '{text}'")
                return None, None
            
        except Exception as e:
            print(f"Error locating {element_type} element '{text}': {e}")
            return None, None

    def move_mouse_to(self, x, y):
        """Move the virtual mouse to the specified coordinates within the browser."""
        print(f" window dimensions: {self.viewport_width}x{self.viewport_height}")
        print(f" last mouse position: {self.last_mouse_position}")
        if self.last_mouse_position is None:
            # If this is the first movement, set the initial position as the current (0, 0)
            self.last_mouse_position = (0, 0)
        if 0 <= x <= self.viewport_width and 0 <= y <= self.viewport_height:
            # Move to the coordinates within the browser window
            offset_x = x - self.last_mouse_position[0]
            offset_y = y - self.last_mouse_position[1]
            self.actions.move_by_offset(offset_x, offset_y).perform()
            self.last_mouse_position = (x, y)
            self.take_screenshot(f"images/screenshot_{x}_{y}.png")
            print(f"Moved mouse to ({x}, {y}) within the browser window.")
            self.last_mouse_position = (x, y)  # Update mouse position
        else:
            print(f"Coordinates ({x}, {y}) are out of browser bounds.")

    def click_at(self, x, y):
        """Move the virtual mouse to (x, y) and perform a click."""
        self.move_mouse_to(x, y)
        self.actions.click().perform()
        print(f"Clicked at ({x}, {y}) within the browser window.")

    def normalize_coordinates(self, x, y, from_screenshot=True):
        """
        Convert coordinates between screenshot (1000x1000) and viewport spaces.
        
        Args:
            x (float): X coordinate
            y (float): Y coordinate
            from_screenshot (bool): If True, convert from screenshot to viewport.
                                  If False, convert from viewport to screenshot.
        
        Returns:
            tuple: (normalized_x, normalized_y)
        """
        if from_screenshot:
            # Convert from 1000x1000 screenshot space to viewport space
            normalized_x = (x * self.viewport_width) / self.screenshot_width
            normalized_y = (y * self.viewport_height) / self.screenshot_height
            print(f"Converting screenshot ({x}, {y}) -> viewport ({normalized_x}, {normalized_y})")
        else:
            # Convert from viewport space to 1000x1000 screenshot space
            normalized_x = (x * self.screenshot_width) / self.viewport_width
            normalized_y = (y * self.screenshot_height) / self.viewport_height
            print(f"Converting viewport ({x}, {y}) -> screenshot ({normalized_x}, {normalized_y})")
        
        return normalized_x, normalized_y

    def take_screenshot(self, filename="images/screenshot.png"):
        """Take a screenshot and overlay coordinate system scaled to 1000x1000."""
        # Take the screenshot
        self.driver.save_screenshot(filename)
        
        try:
            # Open and resize the screenshot to 1000x1000
            image = Image.open(filename)
            draw = ImageDraw.Draw(image)

            try:
                font = ImageFont.truetype("arial.ttf", 15)
            except IOError:
                font = None
            
            # Overlay the mouse position if available
            if self.last_mouse_position:
                # Draw viewport coordinates in red
                viewport_x, viewport_y = self.last_mouse_position
                mouse_size = 10
                draw.ellipse(
                    (viewport_x - mouse_size, viewport_y - mouse_size, 
                     viewport_x + mouse_size, viewport_y + mouse_size),
                    fill='red',
                    outline='black'
                )
                draw.text((viewport_x + 15, viewport_y), 
                         f"Viewport: ({int(viewport_x)}, {int(viewport_y)})", 
                         fill="red", 
                         font=font)
                
                # Draw screenshot coordinates in blue
                screenshot_x, screenshot_y = self.normalize_coordinates(
                    viewport_x, 
                    viewport_y, 
                    from_screenshot=False
                )
                draw.ellipse(
                    (screenshot_x - mouse_size, screenshot_y - mouse_size, 
                     screenshot_x + mouse_size, screenshot_y + mouse_size),
                    fill='blue',
                    outline='black'
                )
                draw.text((screenshot_x + 15, screenshot_y + 25), 
                         f"Screenshot: ({int(screenshot_x)}, {int(screenshot_y)})", 
                         fill="blue", 
                         font=font)

            image = image.resize((self.screenshot_width, self.screenshot_height))
            # Save the modified screenshot
            image.save(filename)
            print(f"Enhanced screenshot saved with viewport and screenshot coordinates at {filename}")
        except Exception as e:
            print(f"Error processing screenshot: {e}")

    def close(self):
        """Close the browser."""
        self.driver.quit()
        print("Browser closed.")

    def type_text(self, text):
        """Type text into the currently focused element."""
        try:
            actions = ActionChains(self.driver)
            actions.send_keys(text)
            actions.perform()
            print(f"Typed text")
            time.sleep(0.5)  # Small delay after typing
        except Exception as e:
            print(f"Error typing text: {e}")

    def press_key(self, key):
        """Press a specific key (e.g., Enter, Tab, etc.)."""
        try:
            actions = ActionChains(self.driver)
            actions.send_keys(getattr(Keys, key.upper()))
            actions.perform()
            print(f"Pressed key: {key}")
            time.sleep(0.5)  # Small delay after key press
        except Exception as e:
            print(f"Error pressing key: {e}")

    def click_and_type(self, x, y, text):
        """Click at coordinates and type text."""
        self.click_at(x, y)
        time.sleep(0.5)  # Wait for click to register
        self.type_text(text)

    def scroll_down(self, amount=300):
        """
        Scroll the page down by the specified amount of pixels.
        Args:
            amount (int): Number of pixels to scroll down. Default is 300.
        """
        try:
            self.driver.execute_script(f"window.scrollBy(0, {amount});")
            print(f"Scrolled down {amount} pixels")
            time.sleep(0.5)  # Small delay after scrolling
            self.take_screenshot()  # Take a screenshot after scrolling
        except Exception as e:
            print(f"Error scrolling down: {e}")

    def scroll_up(self, amount=300):
        """
        Scroll the page up by the specified amount of pixels.
        Args:
            amount (int): Number of pixels to scroll up. Default is 300.
        """
        try:
            self.driver.execute_script(f"window.scrollBy(0, -{amount});")
            print(f"Scrolled up {amount} pixels")
            time.sleep(0.5)  # Small delay after scrolling
            self.take_screenshot()  # Take a screenshot after scrolling
        except Exception as e:
            print(f"Error scrolling up: {e}")

    def scroll_to_element(self, element_text):
        """
        Scroll to make an element with specific text visible.
        Args:
            element_text (str): The text of the element to scroll to
        """
        try:
            element = self.driver.find_element(By.LINK_TEXT, element_text)
            self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
            print(f"Scrolled to element with text: {element_text}")
            time.sleep(0.5)  # Small delay after scrolling
            self.take_screenshot()  # Take a screenshot after scrolling
        except Exception as e:
            print(f"Error scrolling to element: {e}")

    def configure_discord_audio(self):
        """Configure Discord audio settings to prevent echo"""
        try:
            # Navigate to Discord audio settings
            self.driver.execute_script("""
                // Click user settings
                document.querySelector('[aria-label="User Settings"]').click();
                
                // Click Voice & Video settings
                document.querySelector('[aria-label="Voice & Video"]').click();
            """)
            time.sleep(1)
            
            # Configure echo cancellation and noise reduction
            self.driver.execute_script("""
                // Enable echo cancellation
                document.querySelector('[aria-label="Echo Cancellation"]').click();
                
                // Enable noise suppression
                document.querySelector('[aria-label="Noise Suppression"]').click();
                
                // Disable automatic input sensitivity
                document.querySelector('[aria-label="Automatically determine input sensitivity"]').click();
            """)
            
            print("Discord audio settings configured to prevent echo")
            return True
        except Exception as e:
            print(f"Error configuring Discord audio settings: {e}")
            return False

    def save_cookies(self):
        """Save browser cookies to file"""
        try:
            cookies = self.driver.get_cookies()
            os.makedirs('browser_data', exist_ok=True)
            with open('browser_data/cookies.pkl', 'wb') as f:
                pickle.dump(cookies, f)
            print("Cookies saved successfully")
            return True
        except Exception as e:
            print(f"Error saving cookies: {e}")
            return False
            
    def load_cookies(self):
        """Load saved cookies into browser"""
        try:
            if os.path.exists('browser_data/cookies.pkl'):
                with open('browser_data/cookies.pkl', 'rb') as f:
                    cookies = pickle.load(f)
                for cookie in cookies:
                    try:
                        self.driver.add_cookie(cookie)
                    except:
                        continue
                print("Cookies loaded successfully")
                return True
            return False
        except Exception as e:
            print(f"Error loading cookies: {e}")
            return False