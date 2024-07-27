import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
import schedule
import time
import threading
import google.generativeai as genai
from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from contextlib import contextmanager



app = FastAPI()

# Gemini API 설정
load_dotenv()
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-1.5-pro', system_instruction = [
    '너는 아직 일정이 불투명한 이벤트의 발생날짜를 정확히 알기 위해서 주기적으로 확인해 보아야 할 최적의 검색어를 명확히 도출해야해. 검색어를 만들기 위한 충분한 정보가 모일때 까지 사용자에게 질문을 하고, 충분한 정보가 모였다면 검색어를 추천해'
],)
chat = model.start_chat(history = [])
model2 = genai.GenerativeModel('gemini-1.5-flash')


# Database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./preminder.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Database models
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)

class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    search_query = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class ChatHistory(Base):
    __tablename__ = "chat_history"
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"))
    message = Column(String)
    is_user = Column(Boolean)
    timestamp = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@contextmanager
def get_db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Pydantic models
class UserCreate(BaseModel):
    email: str

class EventCreate(BaseModel):
    user_email: str
    event_description: str

class ChatMessage(BaseModel):
    event_id: int
    message: str
    is_user: bool

# API routes
@app.post("/users/")
def create_user(user: UserCreate):
    with get_db_session() as db:
        try:
            db_user = User(email=user.email)
            db.add(db_user)
            db.commit()
            db.refresh(db_user)
            return db_user
        except IntegrityError:
            db.rollback()
            existing_user = db.query(User).filter(User.email == user.email).first()
            if existing_user:
                return existing_user
            raise HTTPException(status_code=400, detail="User creation failed")
    
@app.post("/events/")
def create_event(event: EventCreate):
    with get_db_session() as db:
        user = db.query(User).filter(User.email == event.user_email).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        try:
            # search_query = generate_search_query(event.event_description)
            db_event = Event(user_id=user.id, search_query=event.event_description)
            db.add(db_event)
            db.commit()
            db.refresh(db_event)
            return db_event
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to create event: {str(e)}")

@app.post("/chat/")
def add_chat_message(chat: ChatMessage):
    with get_db_session() as db:
        db_chat = ChatHistory(**chat.dict())
        db.add(db_chat)
        db.commit()
        db.refresh(db_chat)
        return db_chat

# @app.get("/events/")
# def get_user_events(user_email: str):
#     with get_db_session() as db:
#         user = db.query(User).filter(User.email == user_email).first()
#         if not user:
#             raise HTTPException(status_code=404, detail="User not found")
#         events = db.query(Event).filter(Event.user_id == user.id).all()
#         return events

@app.get("/events/{user_email}")
def get_user_events(user_email: str):
    with get_db_session() as db:
        user = db.query(User).filter(User.email == user_email).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        events = db.query(Event).filter(Event.user_id == user.id).all()
        return events

@app.get("/chat/{event_id}")
def get_chat_history(event_id: int):
    with get_db_session() as db:    
        chat_history = db.query(ChatHistory).filter(ChatHistory.event_id == event_id).all()
        return chat_history

@app.delete("/events/{event_id}")
def delete_event(event_id: int):
    with get_db_session() as db:
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")
    
        # Delete related chat history
        db.query(ChatHistory).filter(ChatHistory.event_id == event_id).delete()
        
        # Delete the event
        db.delete(event)
        db.commit()
        return {"message": "Event and related chat history deleted successfully"}

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"message": f"An unexpected error occurred: {str(exc)}"}
    )

# Helper functions (to be implemented)
# def generate_search_query(event_description):
#     prompt = f"Generate an optimal search query for the following event description: '{event_description}'. The query should be specific and include relevant keywords to find information about dates, ticket sales, or announcements related to this event."
#     response = model.generate_content(prompt)
#     return response.text

@app.post("/chat_with_gemini/")
async def chat_with_gemini(request: Request):
    data = await request.json()
    message = data["message"]
    user_email = data["user_email"]
    
    with get_db_session() as db:
        user = db.query(User).filter(User.email == user_email).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        if 'chat_history' not in globals():
            global chat_history
            chat_history = []
        
        # chat = model.start_chat(history = [])
        # prompt = f"{message}"
        response = chat.send_message(message)
        chat_history.append({"user": message, "assistant": response.text})
        return {"response": response.text}

@app.post("/finalize_search_query/")
async def finalize_search_query(request: Request):
    data = await request.json()
    user_email = data["user_email"]
    
    with get_db_session() as db:
        user = db.query(User).filter(User.email == user_email).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        full_history = "\n".join([f"User: {msg['user']}\nAssistant: {msg['assistant']}" for msg in chat_history])
        prompt = f"{full_history} \n\n 위에 입력된 대화를 보고 마지막 부분에서 도출된 최종 검색어 단 한개 만을 출력해"
        
        response = model2.generate_content(prompt)
        final_query = response.text.strip()
        
        return {"final_query": final_query}

@app.post("/confirm_search_query/")
async def confirm_search_query(request: Request):
    data = await request.json()
    user_email = data["user_email"]
    final_query = data["final_query"]
    
    chat = model.start_chat(history = [])
    
    with get_db_session() as db:
        user = db.query(User).filter(User.email == user_email).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        new_event = Event(user_id=user.id, search_query=final_query)
        db.add(new_event)
        db.commit()
        db.refresh(new_event)
        
        global chat_history
        chat_history = []
        
        return {"message": "Search query confirmed and saved", "event_id": new_event.id}

def search_google(query):
    prompt = f"Search for the following query and provide the top 3 most relevant results: '{query}'. Format the results as a list of dictionaries with 'title' and 'snippet' keys."
    response = model.generate_content(prompt)
    results = eval(response.text)  # 주의: 실제 환경에서는 더 안전한 방법으로 파싱해야 합니다.
    return results

def send_email(to_email, subject, body):
    # Send email using SMTP
    # This is a placeholder function
    print(f"Sending email to {to_email}")
    print(f"Subject: {subject}")
    print(f"Body: {body}")

def check_events():
    with get_db_session() as db:
        events = db.query(Event).all()
        for event in events:
            results = search_google(event.search_query)
            if has_relevant_info(results):
                user = db.query(User).filter(User.id == event.user_id).first()
                send_email(user.email, "Event Update", f"New information found for your event: {event.search_query}")

def has_relevant_info(results, query):
    prompt = f"Analyze the following search results for the query '{query}' and determine if they contain relevant new information about event dates, ticket sales, or announcements. Respond with 'True' if relevant information is found, otherwise 'False'.\n\nResults: {results}"
    response = model.generate_content(prompt)
    return response.text.strip().lower() == 'true'

def format_results(results):
    formatted = ""
    for i, result in enumerate(results, 1):
        formatted += f"{i}. {result['title']}\n   {result['snippet']}\n\n"
    return formatted

# Schedule daily task
schedule.every().day.at("00:00").do(check_events)

# Run scheduled tasks in a separate thread
def run_schedule():
    while True:
        schedule.run_pending()
        time.sleep(1)

threading.Thread(target=run_schedule, daemon=True).start()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)