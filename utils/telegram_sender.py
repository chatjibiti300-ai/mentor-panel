from aiogram import Bot
from aiogram.types import FSInputFile
from config import BOT_TOKEN

bot = Bot(token=BOT_TOKEN)


async def send_text(chat_id, text):
    await bot.send_message(chat_id, text)


async def send_photo(chat_id, file_id, caption=None):
    await bot.send_photo(chat_id, photo=file_id, caption=caption)


async def send_document(chat_id, file_id, caption=None):
    await bot.send_document(chat_id, document=file_id, caption=caption)


# Kompyuterdan yuklangan rasmni yuborish
async def send_local_photo(chat_id, file_path, caption=None):
    photo = FSInputFile(file_path)
    await bot.send_photo(chat_id, photo=photo, caption=caption)


# Kompyuterdan yuklangan faylni yuborish
async def send_local_document(chat_id, file_path, caption=None):
    document = FSInputFile(file_path)
    await bot.send_document(chat_id, document=document, caption=caption)