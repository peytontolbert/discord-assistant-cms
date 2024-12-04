from flask import Flask, render_template, request, jsonify
import os
from dotenv import load_dotenv
from computer.browser import BrowserController
from pipelines.discord import login, click_join_voice
from modes.play_mp3_file import play_audio_file
from pipelines.youtube import YouTubeManager
from modes.conversation import ConversationManager
import threading
import time
import json
import sounddevice as sd
from threading import Lock
import sys
import logging
import subprocess
from pathlib import Path
from fivetts.tts_service import F5TTSService

# Load environment variables
load_dotenv()

# After imports, before creating Flask app
def setup_audio_devices():
    """Configure audio devices before starting the application"""
    try:
        # Define ears and voice device names via environment variables
        ears_device_name = os.getenv('EARS_DEVICE_NAME', 'CABLE Output (VB-Audio Virtual Cable)')  # Input device for ears
        voice_device_name = os.getenv('VOICE_DEVICE_NAME', 'CABLE Input (VB-Audio Virtual Cable)')   # Output device for TTS voice
        
        # Retrieve list of all audio devices
        devices = sd.query_devices()
        
        # Find ears device by name (input)
        input_device = next(
            (i for i, d in enumerate(devices) if ears_device_name in d['name'] and d['max_input_channels'] > 0),
            None
        )
        
        # Find voice device by name (output)
        output_device = next(
            (i for i, d in enumerate(devices) if voice_device_name in d['name'] and d['max_output_channels'] > 0),
            None
        )
        
        if input_device is None:
            print(f"Ears device '{ears_device_name}' not found. Please verify the device name and try again.")
            return None
        
        if output_device is None:
            print(f"Voice device '{voice_device_name}' not found. Please verify the device name and try again.")
            return None
        
        # Assign the found devices to input and output
        config = {
            'input_device': input_device,
            'output_device': output_device, 
            'sample_rate': int(sd.query_devices(input_device, 'input')['default_samplerate']),
            'input_sample_rate': int(sd.query_devices(input_device, 'input')['default_samplerate']),
            'output_sample_rate': int(sd.query_devices(output_device, 'output')['default_samplerate'])
        }
        
        print(f"\nAudio configuration: {config}")
        return config
    
    except Exception as e:
        print(f"Error setting up audio devices: {e}")
        return None

# Initialize audio before creating the assistant
audio_config = setup_audio_devices()
if not audio_config:
    print("Failed to configure audio devices. Please check your VB-Audio Cable installation.")
    sys.exit(1)

app = Flask(__name__)

# Store Discord credentials and settings
DISCORD_USER = os.getenv('DISCORD_USER')
DISCORD_PASS = os.getenv('DISCORD_PASS')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
CHANNELS_FILE = 'channels.json'
SETTINGS_FILE = 'settings.json'

class DiscordAssistant:
    _instance = None
    _lock = Lock()
    _initialized = False
    
    def __new__(cls, audio_config):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(DiscordAssistant, cls).__new__(cls)
            return cls._instance

    def __init__(self, audio_config):
        with self._lock:
            if self._initialized:
                return
                
            self.audio_config = audio_config
            self.browser = None
            self.current_mode = None
            self.stop_event = threading.Event()
            self.audio_thread = None
            self.youtube_manager = None
            self.conversation_manager = ConversationManager(
                openai_api_key=OPENAI_API_KEY,
                audio_config=self.audio_config
            )
            self.mode_threads = {}
            self.channels = self.load_channels()
            self.settings = self.load_settings()
            self.initialize_audio_devices()
            
            # Initialize TTS Service
            self.tts_service = F5TTSService()
            # Configure output device for TTS
            sd.default.device[1] = self.audio_config['output_device']
            
            # Don't initialize browser in __init__
            self._initialized = True
    
    def load_settings(self):
        """Load audio settings from JSON file"""
        try:
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, 'r') as f:
                    return json.load(f)
            return {
                'input_device': None,
                'output_device': None
            }
        except Exception as e:
            print(f"Error loading settings: {e}")
            return {
                'input_device': None,
                'output_device': None
            }
            
    def save_settings(self):
        """Save audio settings to JSON file"""
        try:
            with open(SETTINGS_FILE, 'w') as f:
                json.dump(self.settings, f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving settings: {e}")
            return False

    def initialize_audio_devices(self):
        """Initialize audio devices"""
        try:
            # Get list of audio devices
            devices = sd.query_devices()
            
            # If no devices are selected in settings, try to find VB-Audio devices
            if not self.settings['input_device'] or not self.settings['output_device']:
                for i, device in enumerate(devices):
                    if 'VB-Audio' in device['name']:
                        if device['max_input_channels'] > 0:
                            self.settings['input_device'] = i
                        if device['max_output_channels'] > 0:
                            self.settings['output_device'] = i
                self.save_settings()

            # Set default devices if found
            if self.settings['input_device'] is not None:
                sd.default.device[0] = self.settings['input_device']
            if self.settings['output_device'] is not None:
                sd.default.device[1] = self.settings['output_device']
                
        except Exception as e:
            print(f"Error initializing audio devices: {e}")

    def get_audio_devices(self):
        """Get list of available audio devices"""
        try:
            devices = sd.query_devices()
            input_devices = []
            output_devices = []
            
            for i, device in enumerate(devices):
                device_info = {
                    'id': i,
                    'name': device['name'],
                    'channels': device['max_input_channels'] if device['max_input_channels'] > 0 else device['max_output_channels']
                }
                
                if device['max_input_channels'] > 0:
                    input_devices.append(device_info)
                if device['max_output_channels'] > 0:
                    output_devices.append(device_info)
                    
            return {
                'input_devices': input_devices,
                'output_devices': output_devices,
                'selected_input': self.settings['input_device'],
                'selected_output': self.settings['output_device']
            }
        except Exception as e:
            print(f"Error getting audio devices: {e}")
            return None

    def set_audio_devices(self, input_device, output_device):
        """Set audio input and output devices"""
        try:
            if input_device is not None:
                self.settings['input_device'] = input_device
                sd.default.device[0] = input_device
            if output_device is not None:
                self.settings['output_device'] = output_device
                sd.default.device[1] = output_device
            self.save_settings()
            return True
        except Exception as e:
            print(f"Error setting audio devices: {e}")
            return False

    def load_channels(self):
        """Load channels from JSON file"""
        try:
            if os.path.exists(CHANNELS_FILE):
                with open(CHANNELS_FILE, 'r') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            print(f"Error loading channels: {e}")
            return {}
            
    def save_channels(self):
        """Save channels to JSON file"""
        try:
            with open(CHANNELS_FILE, 'w') as f:
                json.dump(self.channels, f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving channels: {e}")
            return False
            
    def add_channel(self, name, channel_id):
        """Add a new channel to the list"""
        self.channels[name] = channel_id
        return self.save_channels()

    def remove_channel(self, name):
        """Remove a channel from the list"""
        if name in self.channels:
            del self.channels[name]
            return self.save_channels()
        return False
        
    def initialize_browser(self):
        """Initialize browser and login to Discord"""
        with self._lock:
            if self.browser is not None:
                try:
                    self.browser.driver.current_url
                    print("Browser already initialized and responsive")
                    return True
                except Exception as e:
                    print(f"Browser not responsive, cleaning up: {e}")
                    self.cleanup_browser()
            
            try:
                print("Initializing new browser instance...")
                self.browser = BrowserController(
                    window_width=1000, 
                    window_height=1000
                )
                
                
                login(self.browser, DISCORD_USER, DISCORD_PASS)
                return True
                
            except Exception as e:
                print(f"Failed to initialize browser: {e}")
                self.cleanup_browser()
                return False

    def cleanup_browser(self):
        """Clean up browser resources"""
        if self.browser:
            try:
                self.browser.close()
            except Exception as e:
                print(f"Error closing browser: {e}")
            finally:
                self.browser = None

    def cleanup(self):
        """Clean up all resources"""
        self.stop_current_mode()
        self.cleanup_browser()

    def join_channel(self, channel_id):
        """Join a specific Discord channel"""
        if not self.browser:
            return False
        try:
            self.browser.navigate(f"https://discord.com/channels/{channel_id}")
            time.sleep(3)
            return click_join_voice(self.browser)
        except Exception as e:
            print(f"Failed to join channel: {e}")
            return False

    def stop_current_mode(self):
        """Stop the currently running mode"""
        if self.current_mode:
            self.stop_event.set()
            
            # Stop specific mode threads
            if self.current_mode in self.mode_threads:
                thread = self.mode_threads[self.current_mode]
                if thread and thread.is_alive():
                    if self.current_mode == "youtube":
                        self.youtube_manager.stop()
                    elif self.current_mode == "conversation":
                        self.conversation_manager.stop()
                    thread.join(timeout=5)
                self.mode_threads[self.current_mode] = None
            
            # Stop audio thread if it exists
            if self.audio_thread and self.audio_thread.is_alive():
                self.audio_thread.join(timeout=5)
            
            self.stop_event.clear()
            self.current_mode = None

    def start_mode(self, mode, **kwargs):
        """Start a specific mode"""
        self.stop_current_mode()
        self.current_mode = mode
        
        try:
            if mode == "play_audio":
                audio_file = kwargs.get('audio_file')
                if audio_file:
                    self.audio_thread = threading.Thread(
                        target=play_audio_file,
                        args=(audio_file, self.stop_event)
                    )
                    self.audio_thread.start()
                    self.mode_threads[mode] = self.audio_thread
                    return True
                    
            elif mode == "youtube":
                system_prompt = kwargs.get('system_prompt')
                if not self.youtube_manager:
                    self.youtube_manager = YouTubeManager(OPENAI_API_KEY)
                if system_prompt:
                    self.youtube_manager.set_system_prompt(system_prompt)
                
                youtube_thread = self.youtube_manager.start()
                self.mode_threads[mode] = youtube_thread
                return True
                
            elif mode == "conversation":
                system_prompt = kwargs.get('system_prompt')
                audio_config = kwargs.get('audio_config')
                
                # Ensure we have valid audio device info
                if not audio_config or 'input_device' not in audio_config:
                    logging.error("Missing audio configuration")
                    return False
                    
                if not self.conversation_manager:
                    # Initialize conversation manager with the correct devices
                    self.conversation_manager = ConversationManager(
                        openai_api_key=OPENAI_API_KEY,
                        audio_config={
                            'input_device': audio_config['input_device'],  # CABLE Output for listening
                            'output_device': audio_config['output_device'],  # CABLE Input for speaking
                            'sample_rate': audio_config['sample_rate']
                        }
                    )
                    logging.info(f"Created conversation manager with audio config: {audio_config}")
                
                if system_prompt:
                    self.conversation_manager.set_system_prompt(system_prompt)
                
                conversation_thread = self.conversation_manager.start()
                self.mode_threads[mode] = conversation_thread
                return True
                
            # Add other modes here as needed
            
            return False
            
        except Exception as e:
            print(f"Error starting mode {mode}: {e}")
            self.current_mode = None
            return False

    def update_system_prompt(self, system_prompt):
        """Update system prompt for conversation modes"""
        if self.current_mode == "youtube" and self.youtube_manager:
            self.youtube_manager.set_system_prompt(system_prompt)
            return True
        elif self.current_mode == "conversation" and self.conversation_manager:
            self.conversation_manager.set_system_prompt(system_prompt)
            return True
        return False

# Initialize DiscordAssistant with audio_config before starting the browser
assistant = DiscordAssistant(audio_config=audio_config)

# Initialize browser once at startup
if assistant.initialize_browser():
    print("Browser initialized successfully")
else:
    print("Failed to initialize browser")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/channels', methods=['GET'])
def get_channels():
    return jsonify(assistant.channels)

@app.route('/api/channels', methods=['POST'])
def add_channel():
    name = request.json.get('name')
    channel_id = request.json.get('channel_id')
    if not name or not channel_id:
        return jsonify({"success": False, "error": "Name and channel_id required"})
    success = assistant.add_channel(name, channel_id)
    return jsonify({"success": success})

@app.route('/api/channels/<name>', methods=['DELETE'])
def remove_channel(name):
    success = assistant.remove_channel(name)
    return jsonify({"success": success})

@app.route('/api/join_channel', methods=['POST'])
def join_channel():
    channel_name = request.json.get('channel_name')
    if not channel_name in assistant.channels:
        return jsonify({"success": False, "error": "Channel not found"})
    
    # Initialize browser if needed
    if not assistant.browser:
        if not assistant.initialize_browser():
            return jsonify({"success": False, "error": "Failed to initialize browser"})
    
    success = assistant.join_channel(assistant.channels[channel_name])
    return jsonify({"success": success})

@app.route('/api/start_mode', methods=['POST'])
def start_mode():
    mode = request.json.get('mode')
    params = request.json.get('params', {})
    
    if not mode:
        return jsonify({"success": False, "error": "Mode not specified"})
    
    if mode == "conversation":
        params['audio_config'] = audio_config
        success = assistant.start_mode(mode, **params)
        return jsonify({"success": success})
    
    success = assistant.start_mode(mode, **params)
    return jsonify({"success": success})

@app.route('/api/stop', methods=['POST'])
def stop():
    assistant.stop_current_mode()
    return jsonify({"success": True})

@app.route('/api/update_system_prompt', methods=['POST'])
def update_system_prompt():
    system_prompt = request.json.get('system_prompt')
    success = assistant.update_system_prompt(system_prompt)
    return jsonify({"success": success})

@app.route('/api/audio_devices', methods=['GET'])
def get_audio_devices():
    devices = assistant.get_audio_devices()
    return jsonify(devices)

@app.route('/api/audio_devices', methods=['POST'])
def set_audio_devices():
    input_device = request.json.get('input_device')
    output_device = request.json.get('output_device')
    success = assistant.set_audio_devices(input_device, output_device)
    return jsonify({"success": success})

@app.route('/api/browser/status', methods=['GET'])
def get_browser_status():
    if assistant.browser:
        try:
            assistant.browser.driver.current_url
            return jsonify({"initialized": True})
        except:
            return jsonify({"initialized": False})
    return jsonify({"initialized": False})

@app.route('/api/browser/initialize', methods=['POST'])
def init_browser():
    success = assistant.initialize_browser()
    return jsonify({"success": success})

def check_ffmpeg():
    """Check if FFmpeg is available and properly configured"""
    try:
        # Try to run ffmpeg -version
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        print("FFmpeg is available in system PATH")
        return True
    except subprocess.CalledProcessError:
        print("FFmpeg is installed but returned an error")
        return False
    except FileNotFoundError:
        print("FFmpeg not found in system PATH")
        print("Please ensure FFmpeg is installed and added to your system PATH")
        print("You can download FFmpeg from: https://ffmpeg.org/download.html")
        return False

if not os.path.exists('browser_data'):
    os.makedirs('browser_data')

if __name__ == '__main__':
    # Check FFmpeg availability
    if not check_ffmpeg():
        print("WARNING: FFmpeg not properly configured. Some audio features may not work.")
    
    # Initialize browser once at startup
    if assistant.initialize_browser():
        print("Browser initialized successfully")
    else:
        print("Failed to initialize browser")
    
    # Pass audio_config to ConversationManager and WhisperManager
    assistant = DiscordAssistant(audio_config=audio_config)
    
    try:
        # Run Flask with threading enabled
        app.run(debug=False, port=5000, threaded=True, use_reloader=False)
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
        # Stop any active modes
        if assistant.current_mode:
            assistant.stop_current_mode()
        # Cleanup browser
        assistant.cleanup_browser()


