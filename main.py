#DinaraBot Universal 2.0
import openai
import sqlite3
from aiogram import Bot, types
from aiogram.dispatcher import Dispatcher
from aiogram.dispatcher.filters import Text
from aiogram.utils import executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from nltk.metrics.distance import jaccard_distance
import logging
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--bottoken")
parser.add_argument("--oaitoken")
parser.add_argument("--botname")
args = parser.parse_args()

token = args.bottoken
openai.api_key = args.oaitoken


bot = Bot(token)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
logging.basicConfig(filename='bot.log', level=logging.ERROR)

class Form(StatesGroup):
    about = State()

# Connect to the database

conn = sqlite3.connect('context.db')
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS context (token TEXT, context TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS history (token TEXT, chat_id TEXT, message TEXT,utility TEXT)''')
conn.commit()

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.answer("Привет! Начни диалог.")

@dp.message_handler(commands=['settings'])
async def settings(message: types.Message):
    """Conversation entrypoint"""
    # Set state
    try:
        await Form.about.set()
        await message.reply("Опишите, чем должен заниматься бот")
    except Exception as e:
        logging.error("Ошибка записи настроек бота: %s", e)

@dp.message_handler(state=Form.about)
async def process_name(message: types.Message, state: FSMContext):
    """Process user name"""

    # Finish our conversation
    await state.finish()
    cursor.execute("SELECT context FROM context WHERE token = ?",(token[13:],))
    content = cursor.fetchone()
    if content:
        cursor.execute("UPDATE context SET context = ? WHERE token = ?", (message.text, token[13:]))
    else:
        content = message.text
        cursor.execute("INSERT INTO context (token, context) VALUES (?, ?)", (token[13:], message.text))
    conn.commit()

@dp.message_handler()
async def send(message : types.Message):
    # Save the message to the history table
    cursor.execute("INSERT INTO history (token, chat_id, message) VALUES (?, ?, ?)",
                   (token[13:], message.chat.id, message.text))
    conn.commit()
    if message.text.startswith('@DinaraGirl_Bot'):
        # Get the context from the database
        cursor.execute("SELECT context FROM context WHERE token=?", (token[13:],))
        context = cursor.fetchone()
        if context is not None:
            context = context[0]
        else:
            context = ""
        cursor.execute("SELECT message FROM history WHERE token=? AND chat_id=?", (token[13:],message.chat.id,))
        context2 = cursor.fetchall()
        context3 = ""
        for c in context2:
            diffContext = jaccard_distance(set(message.text), set(c[0]))
            if diffContext < 0.5:
                context3 += c[0] + " "
            print(str(diffContext) + ' ' + c[0])
        # print(context3)
        try:
            response = openai.Completion.create(
            model="text-davinci-003",
            prompt=f"{context} {message.text}",
            temperature=0.9,
            max_tokens=3000,
            top_p=1.0,
            frequency_penalty=0.0,
            presence_penalty=0.6,
            stop=["You:"]
            )
            print(message.text)
            print(context)
        except Exception as e:
            logging.error("Ошибка в отправке запроса в OpenAI: %s", e)
            await message.answer('Ошибка запроса. Попробуйте еще раз.')
        try:
            await message.answer(response['choices'][0]['text'])
            # Save the response to the history table
            cursor.execute("INSERT INTO history (token, chat_id, message) VALUES (?, ?, ?)", (token[13:], message.chat.id, response.choices[0].text))
            conn.commit()
        except Exception as e:
            logging.error("Ошибка отправки сообщения-ответа бота в Telegram: %s", e)
            await message.answer('Ошибка запроса. Попробуйте еще раз.')
executor.start_polling(dp, skip_updates=True)
