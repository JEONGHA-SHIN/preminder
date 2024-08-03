import subprocess
import sys

def run_fastapi():
    subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"])

def run_streamlit():
    subprocess.Popen([sys.executable, "-m", "streamlit", "run", "app/app.py"])

if __name__ == "__main__":
    run_fastapi()
    run_streamlit()