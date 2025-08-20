import os
from dotenv import load_dotenv

load_dotenv()  # Load .env file

AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION")

# Debugging (optional - remove after testing)
if not AWS_REGION:
    raise ValueError("❌ AWS_REGION not loaded from .env")
