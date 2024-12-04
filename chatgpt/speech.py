from pathlib import Path
from openai import OpenAI
import time
import shutil

"""
voices:
alloy
echo
fable
onyx
nova
shimmer
"""

class SpeechManager:
    def __init__(self, apikey):
        self.client = OpenAI(api_key=apikey)
        # Ensure the audio directory exists
        audio_dir = Path(__file__).parent.parent / 'static' / 'audio'
        audio_dir.mkdir(parents=True, exist_ok=True)

    def text_to_speech(self, text, voice="alloy"):
        # Save audio files to static/audio/ with a unique timestamp
        speech_file_path = Path(__file__).parent / "speech.wav"
        response = self.client.audio.speech.create(
            model="tts-1",
            voice=voice,
            input=text
        )
        response.stream_to_file(speech_file_path)
        return speech_file_path, response  # Return the path instead of the response

    def save_audio(self, source_path, destination_path):
        """
        Saves the audio file from source_path to destination_path.
        """
        shutil.copy(source_path, destination_path)
