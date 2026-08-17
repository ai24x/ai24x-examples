from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).resolve().parent / ".env", override=True)
import uvicorn
uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)
