"""
MongoDB ନଥିଲେ ଏହି ସରଳ ସଂସ୍କରଣ ବ୍ୟବହାର କରନ୍ତୁ
"""
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import razorpay
import qrcode
from io import BytesIO
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

# Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")

# Simple in-memory database
payments_db = {}
user_states = {}

# Initialize
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
logging.basicConfig(level=logging.INFO)

# Razorpay client
razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

def create_order(amount):
    """Create Razorpay order"""
    amount_paise = int(amount * 100)
    order = razorpay_client.order.create({
        "amount": amount_paise,
        "currency": "INR",
        "payment_capture": 1
    })
    return order

def generate_qr(text):
    """Generate QR code"""
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    bio = BytesIO()
    img.save(bio, 'PNG')
    bio.seek(0)
    return bio

@dp.message_handler(commands=['start'])
async def start(msg: types.Message):
    await msg.reply("Welcome! Use /pay to make payment")

@dp.message_handler(commands=['pay'])
async def pay(msg: types.Message):
    user_states[msg.from_user.id] = "awaiting_amount"
    await msg.reply("Enter amount in INR:")

@dp.message_handler(lambda m: user_states.get(m.from_user.id) == "awaiting_amount")
async def amount(msg: types.Message):
    try:
        amount = float(msg.text)
        user_id = msg.from_user.id
        
        # Create order
        order = create_order(amount)
        order_id = order['id']
        
        # Save to memory
        payments_db[order_id] = {
            'user_id': user_id,
            'amount': amount,
            'status': 'PENDING',
            'created_at': datetime.now()
        }
        
        # Generate QR
        payment_link = f"https://rzp.io/i/{order_id}"
        qr = generate_qr(payment_link)
        
        # Keyboard
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton(
            "✅ Check Payment", 
            callback_data=f"check_{order_id}"
        ))
        
        # Send QR
        await bot.send_photo(
            user_id,
            qr,
            caption=f"Amount: ₹{amount}\nOrder: {order_id[:8]}...",
            reply_markup=keyboard
        )
        
        del user_states[user_id]
        
    except ValueError:
        await msg.reply("Please enter a valid number")

@dp.callback_query_handler(lambda c: c.data.startswith('check_'))
async def check(callback: types.CallbackQuery):
    order_id = callback.data.replace('check_', '')
    
    if order_id in payments_db and payments_db[order_id]['status'] == 'SUCCESS':
        await callback.answer("Already paid!", show_alert=True)
        return
    
    try:
        # Check with Razorpay
        order = razorpay_client.order.fetch(order_id)
        
        if order['status'] == 'paid':
            payments_db[order_id]['status'] = 'SUCCESS'
            await callback.message.edit_caption("✅ Payment confirmed! Thank you!")
            await callback.answer("Payment successful!", show_alert=True)
        else:
            await callback.answer("Payment not received yet!", show_alert=True)
    except:
        await callback.answer("Error checking payment!", show_alert=True)

@dp.message_handler(commands=['history'])
async def history(msg: types.Message):
    user_id = msg.from_user.id
    user_payments = [p for p in payments_db.values() if p['user_id'] == user_id]
    
    if not user_payments:
        await msg.reply("No payment history")
        return
    
    text = "Your payments:\n"
    for p in user_payments[-5:]:
        status = "✅" if p['status'] == 'SUCCESS' else "⏳"
        text += f"{status} ₹{p['amount']}\n"
    
    await msg.reply(text)

async def main():
    print("Bot starting...")
    await dp.start_polling()

if __name__ == '__main__':
    asyncio.run(main())
