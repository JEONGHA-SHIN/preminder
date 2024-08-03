import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    BASE_URL = "http://localhost:8000"
    DATABASE_URL = "sqlite:///./database/preminder.db"
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID")
    SENDER_EMAIL = os.getenv("SENDER_EMAIL")
    EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
    SMTP_SERVER = os.getenv("SMTP_SERVER")
    BATCH_TIME = "08:00"

settings = Settings()