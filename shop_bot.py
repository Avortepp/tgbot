import logging
import aiosqlite
from aiogram.dispatcher.filters import Text
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher import FSMContext
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.contrib.fsm_storage.memory import MemoryStorage
import logging


API_TOKEN = 'token'  # token
admin_id = 'id'  # id

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
dp.middleware.setup(LoggingMiddleware())

reply_keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
buttons = [KeyboardButton(text) for text in [
    'Как сделать заказ?',
    'Сколько времени занимает доставка?',
    'Как оплатить заказ?',
    'Хочу сделать заказ'
]]
reply_keyboard.add(*buttons)

questions_and_answers = {
    'Как сделать заказ?': 'Укажите информацию о заказчике и приложите фото заказа. Вся информация будет передана администратору для проверки и подтверждения заказа, после чего исполнитель приступит к работе.',
    'Сколько времени занимает доставка?': 'От 3 до 10 дней.',
    'Как оплатить заказ?': 'Оплата картой без предоплаты на указанный в оформлении счет. Вся информация проверяется, вы получите подтверждение от админа.'
}

class Form(StatesGroup):
    ORDER = State()

orders = []
orders_sent = False
async def get_orders_today():
    today = datetime.now().date()
    today_orders = [order for order in orders if order['date'].date() == today]
    return today_orders

async def connect_to_db():
    conn = await aiosqlite.connect('orders.db')
    cursor = await conn.cursor()
    await cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT,
            details TEXT,
            date TEXT,
            confirmed INTEGER DEFAULT 0
        )
    ''')
    await conn.commit()
    return conn

async def add_order_to_db(order):
    conn = await connect_to_db()
    cursor = await conn.cursor()
    await cursor.execute('''
        INSERT INTO orders (user, details, date) VALUES (?, ?, ?)
    ''', (order['user'], order['details'], order['date']))
    await conn.commit()
    await conn.close()

async def add_order(order):
    orders.append(order)
    logging.info(f"New order added: {order}")

async def get_unconfirmed_orders():
    conn = await connect_to_db()
    cursor = await conn.cursor()
    await cursor.execute('SELECT * FROM orders WHERE confirmed=0')
    unconfirmed_orders = await cursor.fetchall()
    await conn.close()
    return unconfirmed_orders

async def send_admin_orders(admin_id):
    global orders_sent
    conn = await connect_to_db()
    cursor = await conn.cursor()
    await cursor.execute('SELECT * FROM orders')
    all_orders = await cursor.fetchall()
    await conn.close()

    if all_orders:
        for order in all_orders:
            user_id = order[1]
            order_info = order[2]
            username = order[1]  #  'user'
            user_nickname = order[3]  #  'username' 
            
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(types.InlineKeyboardButton(text="Подтвердить заказ", callback_data=f"confirm_order_{order[0]}"))
            
            # information about order
            await bot.send_message(admin_id, f"Заказ от пользователя {username} (ID: {user_id}):\n{order_info}")
            await bot.send_message(admin_id, f"Никнейм заказчика: {user_nickname}")
            await bot.send_message(admin_id, "Подтвердить заказ?", reply_markup=keyboard)
        
        orders_sent = True
    else:
        orders_sent = False
        # If there are no orders, send a message to the admin
        await bot.send_message(admin_id, "Заказов нет.")
# comand /show_orders
@dp.message_handler(commands=['show_orders'], user_id=admin_id)
async def show_orders(message: types.Message):
    global orders_sent
    if not orders_sent:
        # Get unconfirmed orders from the database and send them to the admin
        await send_admin_orders(admin_id)
    else:
        await bot.send_message(admin_id, "Уже отправлены последние заказы.")

@dp.callback_query_handler(lambda callback_query: callback_query.data.startswith('confirm_order'))
async def process_callback(callback_query: types.CallbackQuery):
    order_id = int(callback_query.data.split('_')[1])
    await bot.send_message(callback_query.from_user.id, "Админ подтвердил ваш заказ!")
# Обработчик для команды /start для админа
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    if str(message.chat.id) == admin_id:
        # For admin we add a button "Show orders"
        view_orders_button = KeyboardButton('Показать заказы')
        markup = ReplyKeyboardMarkup(resize_keyboard=True).add(view_orders_button)
        await message.answer("Приветствую, Админ!", reply_markup=markup)
    else:
        # For normal users we add normal buttons
        reply_keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
        buttons = [KeyboardButton(text) for text in [
            'Как сделать заказ?',
            'Сколько времени занимает доставка?',
            'Как оплатить заказ?',
            'Хочу сделать заказ'
        ]]
        reply_keyboard.add(*buttons)
        await message.answer("Привет! Чтобы сделать заказ, нажмите 'Хочу сделать заказ'.", reply_markup=reply_keyboard)
@dp.message_handler(Text(equals='Хочу сделать заказ'))
async def process_order(message: types.Message):
    await message.answer("Введите информацию для заказа (Имя, Фамилия, Адрес, Фото товара, Номер телефона, Почта):")
    await Form.ORDER.set()
@dp.message_handler(Text(equals='Как сделать заказ?'))
async def answer_order_question(message: types.Message):
    await message.answer(questions_and_answers['Как сделать заказ?'])

# Handler to answer the question "How long does it take to deliver?"
@dp.message_handler(Text(equals='Сколько времени занимает доставка?'))
async def answer_delivery_time_question(message: types.Message):
    await message.answer(questions_and_answers['Сколько времени занимает доставка?'])

# Handler for answering the question "How do I pay for an order?"
@dp.message_handler(Text(equals='Как оплатить заказ?'))
async def answer_payment_question(message: types.Message):
    await message.answer(questions_and_answers['Как оплатить заказ?'])
@dp.message_handler(state=Form.ORDER)
async def get_order_info(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['order_info'] = message.text
        order_data = {
            'user': message.from_user.username,
            'details': message.text,
            'date': datetime.now()
        }
        
        await add_order(order_data)
        
        # Send a message to the user that the order has been accepted
        await message.answer("Заказ успешно принят! Ожидайте подтверждение от админа.")
        
        await send_admin_orders(admin_id)
# ... (Your other code remains unchangedй)

if __name__ == '__main__':
    import asyncio
    loop = asyncio.get_event_loop()
    loop.create_task(dp.start_polling())
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        loop.stop()
        loop.close()