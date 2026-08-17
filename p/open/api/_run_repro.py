from pathlib import Path
try:
    from dotenv import load_dotenv
    load_dotenv(Path("api/.env"))
    print("dotenv loaded")
except Exception as e:
    print("dotenv failed:", e)
import _repro_400
