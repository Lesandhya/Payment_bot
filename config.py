import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Bot Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "payment_bot")

# Payment Settings
MIN_AMOUNT = 1  # Minimum amount in INR
MAX_AMOUNT = 100000  # Maximum amount in INR
PAYMENT_TIMEOUT = 3600  # 1 hour in seconds
