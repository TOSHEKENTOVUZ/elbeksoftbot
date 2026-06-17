import logging, aiosqlite, os
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from openai import AsyncOpenAI

# --- SOZLAMALAR ---
API_TOKEN='8833376973:AAEVLqhv3_gbx8ZVzI92VzjgVeDQgLEcfzE'
OPENAI_API_KEY=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
ADMIN_ID=8958302600

# ------------------

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("bot.log"), logging.StreamHandler()]
)

bot = Bot(token=API_TOKEN, parse_mode=types.ParseMode.HTML)
dp = Dispatcher(bot, storage=MemoryStorage())
DB_PATH = os.path.join(os.getcwd(), 'elbeksoft.db')

class FileAdd(StatesGroup):
    waiting_for_file = State()
    waiting_for_category = State()
    waiting_for_name = State()

async def init_db(_=None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('CREATE TABLE IF NOT EXISTS files (id INTEGER PRIMARY KEY, file_id TEXT, category TEXT, name TEXT)')
        await db.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)')
        await db.commit()
    logging.info("Ma'lumotlar bazasi tayyor.")

async def search_program_online(query: str):
    try:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": "Dastur yuklash linkini top va qisqa javob ber."}, {"role": "user", "content": query}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"AI Error: {e}")
        return "❌ Uzr, AI hozircha javob bera olmayapti."

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (message.from_user.id,))
        await db.commit()
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2).add("💻 Windows", "⚙️ Drivers", "📦 Soft", "🎮 Games", "📊 Statistika")
    await message.answer("ElbekSoft Engine 2.0 faol. 😊\nNima qidiryapsiz?", reply_markup=markup)

@dp.message_handler(lambda m: m.text == "📊 Statistika")
async def stats(message: types.Message):
    async with aiosqlite.connect(DB_PATH) as db:
        f = await (await db.execute("SELECT COUNT(*) FROM files")).fetchone()
        u = await (await db.execute("SELECT COUNT(*) FROM users")).fetchone()
    await message.answer(f"📊 Statistika:\nFayllar bazada: {f[0]}\nObunachilar: {u[0]}")

@dp.message_handler(lambda m: m.text in ["💻 Windows", "⚙️ Drivers", "📦 Soft"])
async def show_files(message: types.Message):
    cat = message.text.split(" ")[1] if " " in message.text else message.text
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT file_id, name FROM files WHERE category=?", (cat,))
        files = await cursor.fetchall()
        if not files: return await message.answer("Ushbu kategoriyada hali fayl yo'q.")
        for f in files: await bot.send_document(message.chat.id, f[0], caption=f[1])

@dp.message_handler(commands=['addfile'])
async def start_add_file(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("Faylni yuboring (bekor qilish uchun /cancel):")
        await FileAdd.waiting_for_file.set()

@dp.message_handler(state='*', commands=['cancel'])
async def cancel_handler(message: types.Message, state: FSMContext):
    await state.finish()
    await message.answer("✅ Jarayon bekor qilindi.")

@dp.message_handler(state=FileAdd.waiting_for_file, content_types=['document'])
async def get_file(message: types.Message, state: FSMContext):
    await state.update_data(file_id=message.document.file_id)
    await message.answer("Kategoriyani yozing (Windows, Drivers, Soft):")
    await FileAdd.waiting_for_category.set()

@dp.message_handler(state=FileAdd.waiting_for_category)
async def get_cat(message: types.Message, state: FSMContext):
    await state.update_data(category=message.text)
    await message.answer("Fayl nomini yozing:")
    await FileAdd.waiting_for_name.set()

@dp.message_handler(state=FileAdd.waiting_for_name)
async def get_name(message: types.Message, state: FSMContext):
    data = await state.get_data()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO files (file_id, category, name) VALUES (?, ?, ?)", 
                         (data['file_id'], data['category'], message.text))
        await db.commit()
    await message.answer("✅ Fayl bazaga muvaffaqiyatli qo'shildi!")
    await state.finish()

@dp.errors_handler()
async def error_handler(update, exception):
    logging.error(f"Kutilmagan xatolik: {exception}")
    return True

@dp.message_handler(lambda m: m.text not in ["💻 Windows", "⚙️ Drivers", "📦 Soft", "🎮 Games", "📊 Statistika"])
async def universal_handler(message: types.Message):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT file_id, name FROM files WHERE name LIKE ?", (f'%{message.text}%',))
        file = await cursor.fetchone()
    if file:
        await bot.send_document(message.chat.id, file[0], caption=f"Bazadan topildi: {file[1]}")
    else:
        msg = await message.answer("🔍 Qidirilmoqda...")
        result = await search_program_online(message.text)
        await bot.edit_message_text(f"🤖 <b>AI Natija:</b>\n\n{result}", chat_id=message.chat.id, message_id=msg.message_id)

if __name__ == '__main__':
    logging.info("Bot ishga tushirildi.")
    executor.start_polling(dp, on_startup=init_db, skip_updates=True)
