#main.py
import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime, timedelta
import schedule
import time
import threading
import google.generativeai as genai
from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from contextlib import contextmanager
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import schedule
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


app = FastAPI()

# Gemini API 설정
load_dotenv()
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-1.5-pro', system_instruction = [
    f"""너는 아직 일정이 불투명한 이벤트의 발생날짜를 정확히 알기 위해서 주기적으로 확인해 보아야 할 최적의 검색어를 명확히 도출해야해. 
    검색어를 만들기 위한 충분한 정보가 모일때 까지 사용자에게 질문을 하고, 충분한 정보가 모였다면 검색어를 추천해. 
    이 과정에서 사용자가 원하는 날짜가 이벤트의 어떤 날짜인지 꼭 포함해야해 (예. 이벤트 발생날짜, 이벤트 접수시작날짜, 이벤트 종료날짜 등)
    """
],)
chat = model.start_chat(history = [])
model2 = genai.GenerativeModel('gemini-1.5-flash')
model3 = genai.GenerativeModel('gemini-1.5-flash', system_instruction = [
    f"""
    Print only accurate answer to given question
    """
    ],)

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
        
        # full_history = "\n".join([f"User: {msg['user']}\nAssistant: {msg['assistant']}" for msg in chat_history])
        # prompt = f"{full_history} \n\n 위에 입력된 대화를 보고 마지막 부분에서 도출된 최종 검색어 단 한개 만을 출력해"
        
        # response = model2.generate_content(prompt)
        prompt = "대화 내용을 토대로, 사용자가 원하는 결과를 찾기에 가장 적합한 단 하나의 최종 검색어를 도춣하여 출력해. 다른 설명은 붙이지마"

        response = chat.send_message(prompt)
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
    try:
        service = build("customsearch", "v1", developerKey=os.getenv('GOOGLE_API_KEY'))
        result = service.cse().list(q=query, cx=os.getenv('GOOGLE_CSE_ID'), num=3).execute()
        
        search_results = []
        if 'items' in result:
            for item in result['items']:
                search_results.append({
                    'title': item['title'],
                    'snippet': item['snippet'],
                    'link': item['link']
                })
        return search_results
    except HttpError as e:
        print(f"An error occurred: {e}")
        return []

def has_relevant_info(results, query):
    today = datetime.now().date()
    combined_results = []
    for result in results:
        analysis_results = {}
        prompt = f"""Analyze the following search result for the query '{query}':
                    {result}
                    For the result, determine:
                    - Topic Relevance: Is the content relevant to the query? (True/False)
                    Please respond the only True/False, except any additional information.
                    """
        
        response = model3.generate_content(prompt)
        analysis_results['topic_relevant'] = response.text.strip().lower()
        
        print("gemini-topic: ", response.text)

        prompt = f"""Analyze the following search result for the query '{query}':
                    {result}
                    For the result, determine:
                    - Future Date: Does it mention any dates after {today}? (True/False)
                    Please respond the only True/False, except any additional information.
                    """
        
        response = model3.generate_content(prompt)
        analysis_results['future_date'] = response.text.strip().lower()
        
        print("gemini-date: ", response.text)
        
        combined_results.append({
            'title': result['title'],
            'snippet': result['snippet'],
            'link': result['link'],
            'topic_relevant': analysis_results['topic_relevant'],
            'future_date': analysis_results['future_date']
        })
    
    return combined_results

def send_email(to_email, subject, body):
    # 이메일 서버 설정
    smtp_server = "smtp.gmail.com"
    port = 587  # Gmail의 TLS 포트
    sender_email = os.getenv("SENDER_EMAIL")  # 발신자 이메일 주소
    password = os.getenv("EMAIL_PASSWORD")  # 발신자 이메일 비밀번호 또는 앱 비밀번호
    print(sender_email, password)
    
    # 이메일 메시지 생성
    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = to_email
    message["Subject"] = subject

    # 이메일 본문 추가
    message.attach(MIMEText(body, "plain"))

    try:
        # SMTP 서버 연결 및 로그인
        server = smtplib.SMTP(smtp_server, port)
        server.starttls()  # TLS 보안 연결
        server.login(sender_email, password)

        # 이메일 발송
        server.send_message(message)
        print(f"Email sent successfully to {to_email}")
    except Exception as e:
        print(f"Error sending email: {e}")
    finally:
        server.quit()  # SMTP 서버 연결 종료
    print(f"Sending email to {to_email}")
    print(f"Subject: {subject}")
    print(f"Body: {body}")

def config_email_body(event):
    results = search_google(event.search_query)
    analyzed_results = has_relevant_info(results, event.search_query)
    
    relevant_results = []
    for r in analyzed_results:
        is_topic_relevant = r['topic_relevant'].lower() == 'true'
        has_future_date = r['future_date'].lower() == 'true'
        
        if is_topic_relevant and has_future_date:
            relevant_results.append(r)
    
    if relevant_results:
        email_body = f"New relevant information found for your event '{event.search_query}':\n\n"
        for r in relevant_results:
            email_body += f"Title: {r['title']}\n"
            email_body += f"Snippet: {r['snippet']}\n"
            email_body += f"Link: {r['link']}\n\n"
        email_body += "이 메일은 preminder에 의해 발송되었습니다."
        return email_body
    
    return None

def check_events():
    with get_db_session() as db:
        events = db.query(Event).all()
        for event in events:
            email_body = config_email_body(event)
            if email_body:
                user = db.query(User).filter(User.id == event.user_id).first()    
                send_email(user.email, f"Event Update: {event.search_query}", email_body)
            time.sleep(60)  # 1분 대기

# def format_results(results):
#     formatted = ""
#     for i, result in enumerate(results, 1):
#         formatted += f"{i}. {result['title']}\n   {result['snippet']}\n\n"
#     return formatted

@app.post("/test_search/")
async def test_search(request: Request):
    data = await request.json()
    query = data["query"]
    
    results = search_google(query)
    print("search results:", results)
    analyzed_results = has_relevant_info(results, query)
    # check_all_events()
    print("last answer:\n", analyzed_results)
    
    # 문자열을 불리언으로 변환하는 함수
    def str_to_bool(s):
        return s.lower() == 'true'
    
    summary = {
        "total_results": len(analyzed_results),
        "relevant_results": sum(1 for r in analyzed_results if str_to_bool(r['topic_relevant'])),
        "future_date_results": sum(1 for r in analyzed_results if str_to_bool(r['future_date'])),
        "relevant_and_future": sum(1 for r in analyzed_results if str_to_bool(r['topic_relevant']) and str_to_bool(r['future_date']))
    }
    
    # 결과를 불리언으로 변환
    for result in analyzed_results:
        result['topic_relevant'] = str_to_bool(result['topic_relevant'])
        result['future_date'] = str_to_bool(result['future_date'])
    
    return {
        "query": query,
        "results": analyzed_results,
        "summary": summary
    }
    
def run_daily_check():
    thread = threading.Thread(target=check_events)
    thread.start()
# Run scheduled tasks in a separate thread
def run_schedule():
    schedule.every().day.at("21:30").do(run_daily_check)
    
    while True:
        schedule.run_pending()
        time.sleep(1)

threading.Thread(target=run_schedule, daemon=True).start()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)