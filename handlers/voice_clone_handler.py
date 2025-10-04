import uuid
from fastapi import UploadFile
from handlers.s3_handler import S3Handler
from app.clients.elevenlabs_client import elevenlabs_client
from app.db.queries import voice_queries

# Initialize the existing S3 Handler
s3_handler = S3Handler()

async def run_full_voice_processing(
    voice_name: str,
    file_contents: bytes,
    original_filename: str,
    text_to_speak: str
) -> tuple | None:
    """
    Handles the entire async workflow for cloning a voice and generating speech.
    """
    # 1. Upload sample voice to S3
    sample_key = f"voice-samples/{uuid.uuid4()}-{original_filename}"
    # Note: We need a new 'upload_bytes' method in the S3Handler for this to work
    upload_result = await s3_handler.upload_bytes(
        file_bytes=file_contents,
        key=sample_key,
        content_type='audio/mpeg'
    )
    if not upload_result or not upload_result.get("success"):
        print("Failed to upload voice sample to S3.")
        return None
    sample_s3_url = upload_result["url"]

    # 2. Clone voice with ElevenLabs
    voice_id = elevenlabs_client.clone_voice(voice_name, "Cloned via API", file_contents, original_filename)
    if not voice_id:
        print("Failed to clone voice with ElevenLabs.")
        return None

    # 3. Save cloned voice record to DB using your async queries
    cloned_voice_record = await voice_queries.add_cloned_voice(
        voice_id=voice_id,
        name=voice_name,
        sample_s3_url=sample_s3_url
    )

    # 4. Generate speech with new voice
    generated_audio_data = elevenlabs_client.generate_speech(voice_id, text_to_speak)
    if not generated_audio_data:
        print("Failed to generate speech with ElevenLabs.")
        return None

    # 5. Upload generated speech to S3
    speech_key = f"speech-outputs/{voice_id}/{uuid.uuid4()}.mp3"
    speech_upload_result = await s3_handler.upload_bytes(
        file_bytes=generated_audio_data,
        key=speech_key,
        content_type='audio/mpeg'
    )
    if not speech_upload_result or not speech_upload_result.get("success"):
        print("Failed to upload generated speech to S3.")
        return None
    speech_s3_url = speech_upload_result["url"]
    
    # 6. Save generated speech record to DB
    await voice_queries.add_generated_speech(
        text=text_to_speak,
        s3_url=speech_s3_url,
        cloned_voice_id=cloned_voice_record["id"]
    )

    return cloned_voice_record, {"s3_url": speech_s3_url}

