# Discord Assistant

A powerful AI-powered Discord assistant that can join voice channels and interact through voice using advanced text-to-speech and speech recognition capabilities.

## Features

- **Voice Channel Integration**: Seamlessly join Discord voice channels
- **Multiple Interaction Modes**:
  - Conversation Mode: Natural voice conversations using OpenAI's GPT models
  - YouTube Mode: Interact with YouTube content (WIP)
  - Audio Playback: Play MP3 files through Discord
- **Advanced Audio Processing**:
  - text-to-speech using F5TTS with zero-shot voice cloning
  - Real-time speech recognition using Whisper
- **Web Interface**:
  - Manage Discord channels
  - Control interaction modes
  - Configure audio devices
  - Update system prompts

## Prerequisites

- Python 3.8+
- FFmpeg installed and added to system PATH
- Microsoft Edge WebDriver
- VB-Audio Virtual Cable (or similar virtual audio device)
- Discord account

## Installation

1. Clone the repository:
```
bash
git clone https://github.com/peytontolbert/discord-assistant-cms
cd discord-assistant-cms
```


2. Install required packages:
```bash
pip install -r requirements.txt
```


3. Set up environment variables in `.env`:
```
env
DISCORD_USER=your_discord_email
DISCORD_PASS=your_discord_password
OPENAI_API_KEY=your_openai_api_key
EARS_DEVICE_NAME=CABLE Output (VB-Audio Virtual Cable)
VOICE_DEVICE_NAME=CABLE Input (VB-Audio Virtual Cable)
```


## Audio Setup

1. Install VB-Audio Virtual Cable:
   - Download from [VB-Audio website](https://vb-audio.com/Cable/)
   - Set up CABLE Output as Discord's audio input
   - Set up CABLE Input as Discord's audio output

2. Configure Discord audio settings:
   - Enable echo cancellation
   - Enable noise suppression
   - Configure input sensitivity

## Usage

1. Start the application:
```bash
python main.py
```


2. Access the web interface at `http://localhost:5000`

3. Through the web interface, you can:
   - Add and manage Discord channels
   - Join voice channels
   - Start different interaction modes
   - Configure audio devices
   - Update system prompts

## Interaction Modes

### Conversation Mode
Natural voice conversations using GPT models and F5TTS for voice synthesis.

### YouTube Mode
Interact with YouTube content through voice commands.

### Audio Playback Mode
Play MP3 files through Discord voice channels.

## Project Structure

- `main.py`: Main application file
- `modes/`: Different interaction mode implementations
- `pipelines/`: Integration with various services
- `ears/`: Audio input processing
- `fivetts/`: Text-to-speech implementation
- `computer/`: Browser automation
- `templates/`: Web interface templates

## Contributing

Contributions are welcome! Please feel free to submit pull requests.

## Acknowledgments

- OpenAI for GPT and Whisper
- F5TTS for text-to-speech capabilities
- VB-Audio for Virtual Cable
- Discord for platform integration
