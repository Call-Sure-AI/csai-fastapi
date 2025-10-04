from pydantic import BaseModel, Field

class VoiceResponse(BaseModel):
    id: int
    voice_id: str
    name: str
    sample_s3_url: str

class CloneAndSpeakResponse(BaseModel):
    message: str
    elevenlabs_voice_id: str
    voice_sample_s3_url: str
    generated_speech_s3_url: str

