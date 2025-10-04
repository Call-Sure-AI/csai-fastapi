import requests
from config import elevenlabs_config

class ElevenLabsClient:
    def __init__(self):
        self.api_key = elevenlabs_config.api_key
        self.base_url = "https://api.elevenlabs.io/v1"
        self._headers = {
            "Accept": "application/json",
            "xi-api-key": self.api_key
        }

    def clone_voice(self, name: str, description: str, file_bytes: bytes, original_filename: str) -> str | None:
        """Clones a voice from bytes and returns the voice_id."""
        url = f"{self.base_url}/voices/add"
        data = {'name': name, 'description': description}
        files = [('files', (original_filename, file_bytes, 'audio/mpeg'))]
        
        response = requests.post(url, headers=self._headers, data=data, files=files)
        
        if response.status_code == 200:
            return response.json().get('voice_id')
        else:
            print(f"Error cloning voice: {response.status_code}\n{response.text}")
            return None

    def generate_speech(self, voice_id: str, text: str) -> bytes | None:
        """Generates speech audio data (bytes)."""
        url = f"{self.base_url}/text-to-speech/{voice_id}"
        json_data = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.6, "similarity_boost": 0.85}
        }
        headers = self._headers.copy()
        headers["Accept"] = "audio/mpeg"
        headers["Content-Type"] = "application/json"
        
        response = requests.post(url, json=json_data, headers=headers)
        
        if response.status_code == 200:
            return response.content
        else:
            print(f"Error generating speech: {response.status_code}\n{response.text}")
            return None

elevenlabs_client = ElevenLabsClient()
