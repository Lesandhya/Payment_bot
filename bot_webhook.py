import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.executor import start_webhook
from datetime import datetime

import config
from database import db
from payments import payment_processor

# Logging setup
logging.basicConfig(level=logging.INFO)

# Environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN", config.BOT_TOKEN)
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")  # Render auto-sets this
PORT = int(os.getenv("PORT", 8000))

# Webhook paths
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL = f"{RENDER_EXTERNAL_URL}{WEBHOOK_PATH}"

# Initialize bot and dispatcher
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

# User states
user_states = {}

def get_payment_keyboard(order_id):
    keyboard = InlineKeyboardMarkup(row_width=1)
    button = InlineKeyboardButton(
        "✅ Check Payment", 
        callback_data=f"check_{order_id}"
    )
    keyboard.add(button)
    return keyboard

@dp.message_handler(commands=['start'])
async def start_command(message: types.Message):
    welcome_text = """
🚀 Welcome to Payment Bot!

Available Commands:
/pay - Make a payment
/history - View payment history
/help - Show help

Made with Python 🐍
    """
    await message.reply(welcome_text)

@dp.message_handler(commands=['pay'])
async def pay_command(message: types.Message):
    user_id = message.from_user.id
    user_states[user_id] = {"state": "awaiting_amount"}
    await message.reply(
        f"💰 Please enter amount in INR:\n"
        f"(₹{config.MIN_AMOUNT} - ₹{config.MAX_AMOUNT})"
    )

@dp.message_handler(lambda message: user_states.get(message.from_user.id, {}).get("state") == "awaiting_amount")
async def process_amount(message: types.Message):
    user_id = message.from_user.id
    
    try:
        amount = float(message.text.strip())
        
        if amount < config.MIN_AMOUNT or amount > config.MAX_AMOUNT:
            await message.reply(
                f"❌ Invalid amount! Please enter between ₹{config.MIN_AMOUNT} and ₹{config.MAX_AMOUNT}:"
            )
            return
        
        # Create Razorpay order
        order = payment_processor.create_order(amount)
        order_id = order['id']
        
        # Save to database
        await db.create_payment(user_id, order_id, amount)
        
        # Payment link and QR code
        payment_link = f"https://rzp.io/i/{order_id}"
        qr_buffer = payment_processor.generate_qr_code(payment_link)
        
        del user_states[user_id]
        
        await message.reply(
            f"✅ Payment request created!\n\n"
            f"Amount: ₹{amount}\n"
            f"Order ID: `{order_id}`\n\n"
            f"Scan QR code or use link below:"
        )
        
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
    order_id = callback_query.data.replace('check_', '')
    user_id = callback_query.from_user.id
    
    await callback_query.answer()
    
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
        order = payment_processor.fetch_order(order_id)
        
        if order['status'] == 'paid':
            await db.update_payment_status(order_id, "SUCCESS")
            
            await callback_query.message.edit_caption(
                callback_query.message.caption,
                reply_markup=None
            )
            
            await bot.send_message(
                user_id,
                f"✅ Payment successful!\n"
                f"Amount: ₹{order['amount']/100}\n"
                f"Thank you for your payment!"
            )
        else:
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
    if message.from_user.id in user_states:
        await message.reply("Please enter amount:")
    else:
        await message.reply("Use /pay to start or /help for help.")

async def on_startup(dp):
    """Webhook startup"""
    await bot.set_webhook(WEBHOOK_URL)
    await db.connect()
    logging.info(f"Webhook set to {WEBHOOK_URL}")

async def on_shutdown(dp):
    """Webhook shutdown"""
    await bot.delete_webhook()
    await db.close()
    logging.info("Webhook removed")

if __name__ == '__main__':
    # Start webhook
    start_webhook(
        dispatcher=dp,
        webhook_path=WEBHOOK_PATH,
        on_startup=on_startup,
        on_shutdown=on_shutdown,
        host='0.0.0.0',
        port=PORT
      )
