from computer.browser import BrowserController
import time
from dotenv import load_dotenv
import os
import sounddevice as sd
import soundfile as sf
import threading
import numpy as np
from selenium.webdriver.common.by import By
from pipelines.discord import login, click_join_voice
from modes.play_mp3_file import play_audio_file
from pipelines.qwenvl import verify_mouse_position, locate_element_coordinates, refine_position_with_history
# Load environment variables
load_dotenv()


# Modified usage example
if __name__ == "__main__":
    # Get Discord credentials
    DISCORD_USER = os.getenv('DISCORD_USER')
    DISCORD_PASS = os.getenv('DISCORD_PASS')

    # Add this near the top with other environment variables
    AUDIO_FILE = os.getenv('AUDIO_FILE', os.path.join(os.path.dirname(__file__), 'audio', 'bane.mp3'))

    print(f"Full audio file path: {os.path.abspath(AUDIO_FILE)}")
    browser = BrowserController(window_width=1000, window_height=1000)
    movement_history = []  # Track movement history for adaptive refinement
    login(browser, DISCORD_USER, DISCORD_PASS)
    # Navigate to specific channel
    time.sleep(3)
    browser.navigate("https://discord.com/channels/811756439420928001/811756439876927499")
    time.sleep(5)  # Wait for channel to load
    
    # Try to join voice channel
    if click_join_voice(browser):
        print("Successfully joined voice channel!")
        
        # Create a stop event for controlling audio playback
        stop_audio = threading.Event()
        
        # Play bane.mp3 through the virtual cable in a loop
        print(f"Starting looped audio playback from: {AUDIO_FILE}")
        audio_thread = threading.Thread(
            target=play_audio_file, 
            args=(AUDIO_FILE, stop_audio)
        )
        audio_thread.start()
        
        try:
            # Keep the script running until interrupted
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping audio playback...")
            stop_audio.set()
            audio_thread.join()
    else:
        print("Failed to join voice channel")

    # Cleanup
    browser.close()