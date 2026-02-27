from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
import config

class Database:
    def __init__(self):
        self.client = None
        self.db = None
    
    async def connect(self):
        """MongoDB ସହିତ ଯୋଗାଯୋଗ କରନ୍ତୁ"""
        self.client = AsyncIOMotorClient(config.MONGODB_URI)
        self.db = self.client[config.DATABASE_NAME]
        
        # Indexes ତିଆରି କରନ୍ତୁ
        await self.db.payments.create_index("order_id", unique=True)
        await self.db.payments.create_index("user_id")
        print("✅ MongoDB connected successfully!")
    
    async def close(self):
        """MongoDB ସହିତ ଯୋଗାଯୋଗ ବନ୍ଦ କରନ୍ତୁ"""
        if self.client:
            self.client.close()
            print("✅ MongoDB connection closed!")
    
    async def create_payment(self, user_id, order_id, amount):
        """ନୂଆ ପେମେଣ୍ଟ ତିଆରି କରନ୍ତୁ"""
        payment = {
            "user_id": user_id,
            "order_id": order_id,
            "amount": amount,
            "status": "PENDING",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        result = await self.db.payments.insert_one(payment)
        return result.inserted_id is not None
    
    async def get_payment(self, order_id):
        """order_id ଦ୍ୱାରା ପେମେଣ୍ଟ ଖୋଜନ୍ତୁ"""
        return await self.db.payments.find_one({"order_id": order_id})
    
    async def update_payment_status(self, order_id, status, payment_details=None):
        """ପେମେଣ୍ଟ ସ୍ଥିତି ଅପଡେଟ୍ କରନ୍ତୁ"""
        update_data = {
            "status": status,
            "updated_at": datetime.utcnow()
        }
        
        if payment_details:
            update_data["payment_details"] = payment_details
        
        result = await self.db.payments.update_one(
            {"order_id": order_id},
            {"$set": update_data}
        )
        
        return result.modified_count > 0
    
    async def is_payment_completed(self, order_id):
        """ପେମେଣ୍ଟ ସଫଳ ହୋଇଛି କି ନାହିଁ ଯାଞ୍ଚ କରନ୍ତୁ"""
        payment = await self.get_payment(order_id)
        return payment and payment["status"] == "SUCCESS"
    
    async def get_user_payments(self, user_id):
        """ବ୍ୟବହାରକାରୀଙ୍କ ସମସ୍ତ ପେମେଣ୍ଟ ଦେଖନ୍ତୁ"""
        cursor = self.db.payments.find({"user_id": user_id}).sort("created_at", -1).limit(10)
        return await cursor.to_list(length=10)

# Database object
db = Database()
