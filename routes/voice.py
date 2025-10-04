from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import List
from handlers import voice_clone_handler
from app.models import voice_schemas  # Corrected import path
from app.db.queries import voice_queries

router = APIRouter()

@router.get("/voices/", response_model=List[voice_schemas.VoiceResponse])
async def get_all_voices():
    """Retrieve a list of all previously cloned voices."""
    voices = await voice_queries.get_all_cloned_voices()
    return voices

@router.post("/clone-and-speak/", response_model=voice_schemas.CloneAndSpeakResponse)
async def clone_and_speak_api(
    voice_name: str = Form(...),
    text_to_speak: str = Form(...),
    file: UploadFile = File(...)
):
    """Upload a voice sample and text to clone and generate speech."""
    if file.content_type not in ["audio/mpeg", "audio/wav", "audio/x-wav"]:
        raise HTTPException(status_code=400, detail="Invalid audio file type.")
    
    file_contents = await file.read()
    
    result = await voice_clone_handler.run_full_voice_processing(
        voice_name=voice_name,
        file_contents=file_contents,
        original_filename=file.filename,
        text_to_speak=text_to_speak
    )

    if not result:
        raise HTTPException(status_code=500, detail="Failed to process voice and generate speech.")

    cloned_voice, generated_speech = result

    return {
        "message": "Voice processed successfully.",
        "elevenlabs_voice_id": cloned_voice["voice_id"],
        "voice_sample_s3_url": cloned_voice["sample_s3_url"],
        "generated_speech_s3_url": generated_speech["s3_url"],
    }

