"""Start the API with uvicorn using HOST / PORT / RELOAD / LOG_LEVEL from .env:  python run.py"""
import uvicorn

from app.config import get_settings

if __name__ == "__main__":
    s = get_settings()
    uvicorn.run("app.main:app", host=s.host, port=s.port, reload=s.reload, log_level=s.log_level)
