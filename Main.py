import os
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from twilio.rest import Client as TwilioClient
from twilio.twiml.voice_response import VoiceResponse
import openai
import firebase_admin
from firebase_admin import credentials, firestore
from fastapi.responses import JSONResponse, PlainTextResponse

# --------- Configuration ---------
# Set these environment variables accordingly
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")  # Your Twilio phone number
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
FIREBASE_CREDENTIALS_FILE = os.getenv("FIREBASE_CREDENTIALS_FILE")  # Path to serviceAccountKey.json

# --------- Initialize Services ---------
# Initialize Twilio client
twilio_client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Initialize OpenAI
openai.api_key = OPENAI_API_KEY

# Initialize Firebase
if not firebase_admin._apps:
    cred = credentials.Certificate(FIREBASE_CREDENTIALS_FILE)
    firebase_admin.initialize_app(cred)
db = firestore.client()

# --------- FastAPI App ---------
app = FastAPI()

# --------- Request Models ---------
class CallRequest(BaseModel):
    phone_number: str
    message: str

class AppointmentRequest(BaseModel):
    client_name: str
    doctor_name: str
    time: str  # Could be ISO 8601 string, e.g. "2025-10-16T10:30:00Z"

# --------- Endpoints ---------

@app.get("/")
async def root():
    """
    Health check endpoint
    """
    return {"message": "Speakeasy running"}

@app.post("/call")
async def make_call(request: CallRequest):
    """
    Make a voice call using Twilio, speaking a message with text-to-speech.
    """
    try:
        # Create TwiML for the call
        response = VoiceResponse()
        response.say(request.message, voice='alice', language='en-US')
        
        # Host your /twiml endpoint somewhere reachable by Twilio, or use TwiML Bins for production.
        # Here, for demo, we use a 'twiml' param with the TwiML inlined.
        call = twilio_client.calls.create(
            to=request.phone_number,
            from_=TWILIO_PHONE_NUMBER,
            twiml=str(response)
        )
        return {"status": "initiated", "sid": call.sid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/appointment")
async def create_appointment(request: AppointmentRequest):
    """
    Store an appointment in Firebase Firestore.
    """
    try:
        doc_ref = db.collection("appointments").add({
            "client_name": request.client_name,
            "doctor_name": request.doctor_name,
            "time": request.time
        })
        return {"status": "success", "appointment_id": doc_ref[1].id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --------- Optional: OpenAI Handler Example (not directly exposed) ---------
async def handle_conversation(prompt: str, model: str = "gpt-3.5-turbo") -> str:
    """
    Use OpenAI API to generate a conversational response.
    """
    try:
        completion = openai.ChatCompletion.create(
            model=model,
            messages=[{"role": "user", "content": prompt}]
        )
        return completion['choices'][0]['message']['content']
    except Exception as e:
        return f"Error: {str(e)}"

# --------- Example Twilio Webhook Endpoint (for real voice conversations) ---------
@app.post("/twilio/voice")
async def twilio_voice(request: Request):
    """
    Example Twilio webhook for receiving and responding to calls with OpenAI.
    """
    form = await request.form()
    speech_result = form.get("SpeechResult", "")
    if speech_result:
        openai_reply = await handle_conversation(speech_result)
    else:
        openai_reply = "Hello, welcome to Speakeasy. How may I assist you?"

    response = VoiceResponse()
    response.say(openai_reply, voice='alice', language='en-US')
    response.listen()
    return PlainTextResponse(str(response), media_type="application/xml")

# --------- Run with: uvicorn main:app --reload ---------

# --------- Notes ---------
# 1. Properly set up your environment variables and Firebase credentials before running.
# 2. For Twilio, your server must be publicly accessible for webhooks (use ngrok for local dev).
# 3. This backend can be expanded to support more conversational features using OpenAI.
