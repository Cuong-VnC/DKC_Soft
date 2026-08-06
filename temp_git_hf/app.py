import uvicorn
from main import app

if __name__ == "__main__":
    # HuggingFace Spaces expects the app to run on host 0.0.0.0 and port 7860
    uvicorn.run("main:app", host="0.0.0.0", port=7860)
