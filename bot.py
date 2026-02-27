import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime

import config
from database import db
from payments import payment_processor

# Logging ସେଟଅପ୍
logging.basicConfig(level=logging.INFO)

# Bot ଏବଂ Dispatcher ଆରମ୍ଭ କରନ୍ତୁ
bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

# ୟୁଜର୍ ସ୍ଥିତି ସଂରକ୍ଷଣ ପାଇଁ
user_states = {}

def get_payment_keyboard(order_id):
    """Check Payment ବଟନ୍ ତିଆରି କରନ୍ତୁ"""
    keyboard = InlineKeyboardMarkup(row_width=1)
    button = InlineKeyboardButton(
        "✅ Check Payment", 
        callback_data=f"check_{order_id}"
    )
    keyboard.add(button)
    return keyboard

@dp.message_handler(commands=['start'])
async def start_command(message: types.Message):
    """Start command - /start"""
    welcome_text = """
🚀 Welcome to Payment Bot!

Available Commands:
/pay - Make a payment
/history - View payment history
/help - Show help

Made with Python 🐍
    """
    await message.reply(welcome_text)

@dp.message_handler(commands=['help'])
async def help_command(message: types.Message):
    """Help command - /help"""
    help_text = f"""
📖 How to use:

1. Click /pay to start payment
2. Enter amount (₹{config.MIN_AMOUNT} - ₹{config.MAX_AMOUNT})
3. Scan QR code or use payment link
4. Click 'Check Payment' after payment
5. Get confirmation

Minimum: ₹{config.MIN_AMOUNT}
Maximum: ₹{config.MAX_AMOUNT}
    """
    await message.reply(help_text)

@dp.message_handler(commands=['pay'])
async def pay_command(message: types.Message):
    """Pay command - /pay"""
    user_id = message.from_user.id
    
    # ୟୁଜର୍ ସ୍ଥିତି ସେଟ୍ କରନ୍ତୁ
    user_states[user_id] = {"state": "awaiting_amount"}
    
    await message.reply(
        f"💰 Please enter amount in INR:\n"
        f"(₹{config.MIN_AMOUNT} - ₹{config.MAX_AMOUNT})"
    )

@dp.message_handler(lambda message: user_states.get(message.from_user.id, {}).get("state") == "awaiting_amount")
async def process_amount(message: types.Message):
    """Amount input process କରନ୍ତୁ"""
    user_id = message.from_user.id
    
    try:
        amount = float(message.text.strip())
        
        # Amount ଯାଞ୍ଚ କରନ୍ତୁ
        if amount < config.MIN_AMOUNT or amount > config.MAX_AMOUNT:
            await message.reply(
                f"❌ Invalid amount! Please enter between ₹{config.MIN_AMOUNT} and ₹{config.MAX_AMOUNT}:"
            )
            return
        
        # Razorpay order ତିଆରି କରନ୍ତୁ
        order = payment_processor.create_order(amount)
        order_id = order['id']
        
        # Database ରେ ସେଭ୍ କରନ୍ତୁ
        await db.create_payment(user_id, order_id, amount)
        
        # Payment link ଏବଂ QR code
        payment_link = f"https://rzp.io/i/{order_id}"  # Simple link
        qr_buffer = payment_processor.generate_qr_code(payment_link)
        
        # ୟୁଜର୍ ସ୍ଥିତି ସଫା କରନ୍ତୁ
        del user_states[user_id]
        
        # Payment details ପଠାନ୍ତୁ
        await message.reply(
            f"✅ Payment request created!\n\n"
            f"Amount: ₹{amount}\n"
            f"Order ID: `{order_id}`\n\n"
            f"Scan QR code or use link below:"
        )
        
        # QR code ପଠାନ୍ତୁ
        await bot.send_photo(
            chat_id=user_id,
            photo=qr_buffer,
            caption=f"🔗 {payment_link}",
            reply_markup=get_payment_keyboard(order_id)
        )
        
    except ValueError:
        await message.reply("❌ Please enter a valid number:")
    except Exception as e:
        logging.error(f"Error: {e}")
        await message.reply("❌ Something went wrong. Please try again.")
        if user_id in user_states:
            del user_states[user_id]

@dp.callback_query_handler(lambda c: c.data.startswith('check_'))
async def check_payment(callback_query: types.CallbackQuery):
    """Check payment button handler"""
    order_id = callback_query.data.replace('check_', '')
    user_id = callback_query.from_user.id
    
    await callback_query.answer()
    
    # ପ୍ରଥମେ ଯାଞ୍ଚ କରନ୍ତୁ ଯେ ପେମେଣ୍ଟ ପୂର୍ବରୁ ସଫଳ ହୋଇଛି କି
    if await db.is_payment_completed(order_id):
        await callback_query.message.edit_caption(
            callback_query.message.caption,
            reply_markup=None
        )
        await bot.send_message(
            user_id,
            "✅ Payment already confirmed! Thank you!"
        )
        return
    
    try:
        # Razorpay ରୁ order details ଆଣନ୍ତୁ
        order = payment_processor.fetch_order(order_id)
        
        # Payment status ଯାଞ୍ଚ କରନ୍ତୁ
        if order['status'] == 'paid':
            # Database update କରନ୍ତୁ
            await db.update_payment_status(order_id, "SUCCESS")
            
            # Button ହଟାନ୍ତୁ
            await callback_query.message.edit_caption(
                callback_query.message.caption,
                reply_markup=None
            )
            
            # Success message
            await bot.send_message(
                user_id,
                f"✅ Payment successful!\n"
                f"Amount: ₹{order['amount']/100}\n"
                f"Thank you for your payment!"
            )
        else:
            # Payment ମିଳିଲା ନାହିଁ
            await bot.send_message(
                user_id,
                "❌ Payment not received yet.\n"
                "Please complete the payment and try again."
            )
            
    except Exception as e:
        logging.error(f"Error checking payment: {e}")
        await bot.send_message(
            user_id,
            "❌ Error checking payment. Please try again later."
        )

@dp.message_handler(commands=['history'])
async def history_command(message: types.Message):
    """History command - /history"""
    user_id = message.from_user.id
    
    payments = await db.get_user_payments(user_id)
    
    if not payments:
        await message.reply("📭 No payment history found.")
        return
    
    history_text = "📊 Your Payment History:\n\n"
    
    for p in payments:
        status = "✅" if p['status'] == "SUCCESS" else "⏳"
        date = p['created_at'].strftime("%d-%b-%Y")
        history_text += f"{status} ₹{p['amount']} - {date}\n"
    
    await message.reply(history_text)

@dp.message_handler()
async def unknown_message(message: types.Message):
    """Unknown messages handler"""
    if message.from_user.id in user_states:
        await message.reply("Please enter amount:")
    else:
        await message.reply("Use /pay to start or /help for help.")

async def main():
    """Main function"""
    # Database connect କରନ୍ତୁ
    await db.connect()
    
    # Bot start କରନ୍ତୁ
    print("🤖 Bot is starting...")
    await dp.start_polling()

if __name__ == '__main__':
    asyncio.run(main())
