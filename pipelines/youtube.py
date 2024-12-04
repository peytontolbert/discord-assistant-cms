import os
import threading
import time
from ears.whisper_manager import WhisperManager
from chatgpt.text import TextManager
from chatgpt.speech import SpeechManager
import re
from collections import deque
import sounddevice as sd
import soundfile as sf
import numpy as np
import yt_dlp
import logging

class YouTubeManager:
    def __init__(self, openai_api_key):
        self.whisper = WhisperManager(threshold=0.03)
        self.text_manager = TextManager(openai_api_key)
        self.speech_manager = SpeechManager(openai_api_key)
        self.conversation_history = deque(maxlen=5)  # Keep last 5 messages
        self.stop_event = threading.Event()
        self.system_prompt = "You are a helpful assistant named Bob."
        
        # Set up audio devices
        self.input_device, self.output_device = self.setup_audio_devices()
        print(f"Using audio devices - Input: {self.input_device}, Output: {self.output_device}")
        
        # Create directories if they don't exist
        self.audio_dir = os.path.join(os.path.dirname(__file__), '..', 'static', 'audio')
        os.makedirs(self.audio_dir, exist_ok=True)
        
        # Configure yt-dlp options
        self.ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': os.path.join(self.audio_dir, '%(title)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True
        }

    def set_system_prompt(self, prompt):
        """Allow user to set the system prompt for the conversation"""
        self.system_prompt = prompt
        print(f"System prompt updated to: {prompt}")

    def setup_audio_devices(self):
        """Find and set up VB-Audio Cable devices"""
        try:
            devices = sd.query_devices()
            input_device = None
            output_device = None
            
            # Find VB-Audio devices
            for i, device in enumerate(devices):
                if 'VB-Audio' in device['name']:
                    # Cable Input is what we want to listen to (it's an input device)
                    if device['max_input_channels'] > 0 and 'Cable' in device['name']:
                        input_device = i
                    # Cable Output is what we want to output to (it's an output device)
                    if device['max_output_channels'] > 0:
                        output_device = i
            
            if input_device is not None and output_device is not None:
                # Set default devices
                sd.default.device = [input_device, output_device]
                # Re-initialize whisper with the correct input device
                self.whisper = WhisperManager(threshold=0.03, input_device=input_device)
                return input_device, output_device
            else:
                print("Warning: VB-Audio devices not found, using system defaults")
                return sd.default.device
                
        except Exception as e:
            print(f"Error setting up audio devices: {e}")
            return sd.default.device

    def transcribe_audio_stream(self):
        """Continuously transcribe audio and look for commands"""
        try:
            def audio_callback(indata, frames, time_info, status):
                if status:
                    logging.error(f"Audio status: {status}")
                    return
                
                try:
                    # Process the audio data
                    audio_data = indata.flatten()
                    audio_level = np.max(np.abs(audio_data))
                    
                    if audio_level > self.whisper.threshold:
                        # Use record_audio instead of process_audio
                        transcription = self.whisper.record_audio(
                            audio_data,
                            sample_rate=self.sample_rate,
                            channels=self.channels
                        )
                        
                        if transcription:
                            logging.info(f"User said: {transcription}")
                            
                            # Check for "hey bob" command
                            if "hey bob" in transcription.lower():
                                # Extract the song request
                                song_request = transcription.lower().split("hey bob")[1].strip()
                                self.handle_song_request(song_request)
                            else:
                                # Handle as conversation
                                self.conversation_history.append({
                                    "role": "user",
                                    "content": transcription
                                })
                                self.generate_response(transcription)
                
                except Exception as e:
                    logging.error(f"Error in audio callback: {e}")

            # Start audio stream
            try:
                with sd.InputStream(
                    device=self.input_device,
                    callback=audio_callback,
                    **self.stream_config
                ) as stream:
                    logging.info("Started listening for YouTube commands")
                    while not self.stop_event.is_set():
                        time.sleep(0.1)
                        
            except sd.PortAudioError as e:
                logging.error(f"Audio stream error: {e}")
                print("Error: Could not open audio stream. Check your audio devices.")
                
        except Exception as e:
            logging.error(f"Transcription stream error: {e}")

    def handle_song_request(self, request):
        """Process song request and search YouTube"""
        try:
            # Use TextManager to interpret the song request
            search_prompt = """
            Convert this voice command into a YouTube music search query.
            Remove any unnecessary words and focus on artist and song title.
            Example: "can you play happy by pharrell" -> "pharrell williams happy official audio"
            Request: {request}
            Response format: Just the search query, no explanation.
            """.format(request=request)
            
            search_query = self.text_manager.text_to_text(
                system_prompt="You are a music search query optimizer.",
                user_prompt=search_prompt
            ).content.strip()
            
            print(f"Searching YouTube for: {search_query}")
            
            # Search and play the video
            self.search_and_play_youtube(search_query)
            
        except Exception as e:
            print(f"Error handling song request: {e}")

    def search_and_play_youtube(self, query):
        """Search YouTube and play the first result"""
        try:
            # Construct search URL
            search_url = f"ytsearch1:{query}"
            
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                # Get video info first
                info = ydl.extract_info(search_url, download=False)
                if 'entries' in info:
                    video = info['entries'][0]
                else:
                    video = info
                    
                # Download the audio
                print(f"Downloading: {video['title']}")
                ydl.download([search_url])
                
                # Get the output file path
                output_file = os.path.join(
                    self.audio_dir, 
                    f"{video['title']}.mp3"
                )
                
                # Play the downloaded file
                if os.path.exists(output_file):
                    self.play_audio_file(output_file)
                    # Clean up old files
                    self.cleanup_audio_files(except_file=output_file)
                else:
                    raise Exception("Downloaded file not found")
                
        except Exception as e:
            print(f"Error in YouTube search and play: {e}")
            self.speak("Sorry, I couldn't play that song.")

    def cleanup_audio_files(self, except_file=None):
        """Clean up old audio files except the current one"""
        try:
            for file in os.listdir(self.audio_dir):
                file_path = os.path.join(self.audio_dir, file)
                if file_path != except_file and file.endswith('.mp3'):
                    os.remove(file_path)
        except Exception as e:
            print(f"Error cleaning up audio files: {e}")

    def play_audio_file(self, file_path):
        """Play audio file through virtual audio cable"""
        try:
            # Load the audio file
            data, samplerate = sf.read(file_path)
            
            # Convert to float32 if needed
            if data.dtype != np.float32:
                data = data.astype(np.float32)
            
            # If stereo, convert to mono
            if len(data.shape) > 1:
                data = np.mean(data, axis=1)
            
            # Play through configured output device
            with sd.OutputStream(
                channels=1, 
                samplerate=samplerate, 
                device=self.output_device
            ) as stream:
                stream.write(data)
                
        except Exception as e:
            print(f"Error playing audio: {e}")

    def generate_response(self, user_input):
        """Generate and speak assistant response"""
        try:
            # Prepare conversation history for API
            messages = list(self.conversation_history)
            
            # Get assistant response
            response = self.text_manager.text_to_text(
                system_prompt=self.system_prompt,
                user_prompt=user_input
            )
            
            # Add response to history
            self.conversation_history.append({"role": "assistant", "content": response.content})
            
            # Convert response to speech
            speech_file, _ = self.speech_manager.text_to_speech(response.content)
            
            # Play response through virtual audio cable
            self.play_audio_file(speech_file)
            
        except Exception as e:
            print(f"Error generating response: {e}")

    def stop(self):
        """Stop all ongoing operations"""
        self.stop_event.set()

    def start(self):
        """Start the YouTube manager"""
        self.stop_event.clear()
        
        # Start transcription thread
        transcription_thread = threading.Thread(
            target=self.transcribe_audio_stream
        )
        transcription_thread.start()
        
        return transcription_thread

    def speak(self, text):
        """Utility method to speak text responses"""
        try:
            speech_file, _ = self.speech_manager.text_to_speech(text)
            self.play_audio_file(speech_file)
        except Exception as e:
            print(f"Error in speak method: {e}")
