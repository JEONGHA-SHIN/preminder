import subprocess
import sys
from app.main import start_scheduler
import threading
import time

def run_process(command, prefix):
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1
    )
    for line in iter(process.stdout.readline, ''):
        print(f"{prefix}: {line}", end='')

def run_fastapi():
    command = [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
    run_process(command, "FastAPI")

def run_streamlit():
    command = [sys.executable, "-m", "streamlit", "run", "app/app.py"]
    run_process(command, "Streamlit")

if __name__ == "__main__":
    start_scheduler()  # 스케줄러 시작
    print("Scheduler started")

    fastapi_thread = threading.Thread(target=run_fastapi)
    streamlit_thread = threading.Thread(target=run_streamlit)


    fastapi_thread.start()
    streamlit_thread.start()
    
    # 메인 스레드 유지
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down...")