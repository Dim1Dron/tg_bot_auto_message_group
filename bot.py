from aiogram import executor, Dispatcher, types, Bot
from aiogram.utils import exceptions
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import StatesGroup, State
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.dispatcher.filters import Text
import config
import sqlite3

# Подключение базы данных
con = sqlite3.connect("database.db")
cursor = con.cursor()

#-Временный контейнер-
storage = MemoryStorage()

# Инициализация бота
bot = Bot(config.TOKEN_API)
dp = Dispatcher(bot, storage=storage)

# Функция при запуске бота
async def on_startup(_):
    print("Бот запущен!")

# Получение числа из базы данных
def get_number_of_messages(message):
    cursor.execute(f"SELECT * FROM number_of_messages WHERE id ={message.chat.id}")
    result = cursor.fetchone()
    if result is not None:
        return result[2]
    else:
        # Обработка случая, когда запрос не вернул результатов
        return None

class MainState(StatesGroup):

    admin_check = State()
    admin_settings = State()
    admin_settings_chat = State()
    admin_settings_photo = State()
    admin_settings_bn = State()
    admin_settings_photo_url = State()
    admin_settings_chat_number = State()
    admin_settings_bn_set = State()
    admin_settings_bn_set_sp2 = State()
    admin_settings_bn_set_final = State()
    admin_settings_bn_del = State()
    admin_settings_bn_set_data = State()
    admin_settings_bn_set_data_set = State()
    admin_settings_bn_set_data_set_final = State()

# Словарь для хранения количества отправленных сообщений в каждом чате
messages_count = {}

# Словарь для хранения идентификаторов предыдущих сообщений с фотографией
prev_photo_messages = {}

# Функция для отправки сообщения оповещения и удаления предыдущего
async def send_notification(chat_id, message_id, message):
    try:
        if message_id:
            await bot.delete_message(chat_id, message_id)
        if chat_id in prev_photo_messages:
            await bot.delete_message(chat_id, prev_photo_messages[chat_id])
        
        cursor.execute(f"SELECT * FROM main_keyboard WHERE id ={message.chat.id}")
        rows = cursor.fetchall()
        ikb = InlineKeyboardMarkup(resize_keyboard=True)
        for row in rows:
            ikb.add(InlineKeyboardButton(text=row[2], url=row[3]))

        cursor.execute(f"SELECT * FROM main WHERE id ={message.chat.id}")
        row = cursor.fetchone()
        if row:
            sent_message = await bot.send_photo(chat_id, row[2], reply_markup=ikb)
            prev_photo_messages[chat_id] = sent_message.message_id
    except exceptions.MessageToDeleteNotFound:
        pass


async def check_public(message: types.Message):
    cursor.execute(f"SELECT * FROM number_of_messages WHERE id ={message.chat.id}")
    rows = cursor.fetchall()
    if rows == []:
        if str(message.chat.id).startswith('-'):
            cursor.execute("INSERT INTO number_of_messages (id, title, number) VALUES (?, ?, ?)", (message.chat.id, message.chat.title, config.NUMBER_MESSAGE))
            con.commit()
    else:
        cursor.execute(f"SELECT * FROM main WHERE id ={message.chat.id}")
        rows = cursor.fetchall()
        if rows == []:
            cursor.execute("INSERT INTO main (id, title, url) VALUES (?, ?, ?)", (message.chat.id, message.chat.title, config.PHOTO_URL))
            con.commit()
        else:
            cursor.execute(f"SELECT * FROM main_keyboard WHERE id ={message.chat.id}")
            rows = cursor.fetchall()
            if rows == []:
                cursor.execute("INSERT INTO main_keyboard (id, title, name, url) VALUES (?, ?, ?, ?)", (message.chat.id, message.chat.title, config.BUTTON_NAME, config.BUTTON_URL))
                con.commit()
            else:
                return None

@dp.message_handler(commands='admin', state='*')
async def cmd_admin(message: types.Message):
    await bot.send_message(chat_id=message.from_user.id,
                           text="Для подтверждения прав введите пароль")
    await MainState.admin_check.set()

kb = ReplyKeyboardMarkup()
kb.add(KeyboardButton("Изменить периодичность отправки"))
kb.add(KeyboardButton("Изменить фотографию"))
kb.add(KeyboardButton("Изменить кнопки"))

# Обработчик всех сообщений
@dp.message_handler(state=MainState.admin_check)
async def check_admin(message: types.Message):
    global kb
    if config.ADMIN_PASSWORD == message.text:
        await bot.send_message(chat_id=message.from_user.id,
                               text="Выберите опцию:",
                               reply_markup=kb)
        await MainState.admin_settings.set()
    else:
        await bot.send_message(chat_id=message.from_user.id,
                         text="Неправильный пароль.")


@dp.message_handler(Text(equals='Изменить кнопки'), state=MainState.admin_settings)
async def settings_bn(message: types.Message):
    cursor.execute(f"SELECT DISTINCT title FROM main_keyboard")  # Выбираем уникальные значения
    unique_rows = cursor.fetchall()
    
    kb = ReplyKeyboardMarkup()
    for row in unique_rows:
        kb.add(KeyboardButton(f'{row[0]}'))  # Добавляем уникальные значения в клавиатуру
    
    await bot.send_message(chat_id=message.from_user.id,
                           text="Выберите чат:",
                           reply_markup=kb)
    await MainState.admin_settings_bn.set()

name_public = None
@dp.message_handler(state=MainState.admin_settings_bn)
async def settings_bn_public(message: types.Message):
    global name_public
    cursor.execute(f"SELECT * FROM main_keyboard")
    row = cursor.fetchall()
    name_public = message.text
    await bot.send_message(chat_id=message.from_user.id,
                               text=f"Для группы {name_public} бот имеет следующие кнопки:")
    for rows in row:
        if message.text == rows[1]:
            name_public = rows[1]
            await bot.send_message(chat_id=message.from_user.id,
                               text=f"{rows[2]}: {rows[3]}")
    kb = ReplyKeyboardMarkup()
    kb.add(KeyboardButton("Добавить кнопку"))
    kb.add(KeyboardButton("Удалить кнопку"))
    kb.add(KeyboardButton("Изменить кнопку"))
    await bot.send_message(chat_id=message.from_user.id,
                               text="Выберите опцию:",
                               reply_markup=kb)
    await MainState.admin_settings_bn_set.set()


@dp.message_handler(Text(equals='Изменить кнопку'), state=MainState.admin_settings_bn_set)
async def settings_bn_public_set(message: types.Message):
    global name_public
    cursor.execute(f"SELECT * FROM main_keyboard WHERE title = '{name_public}'")
    row = cursor.fetchall()
    kb = ReplyKeyboardMarkup()
    for rows in row:
        kb.add(KeyboardButton(f'{rows[2]}: {rows[3]}'))
    await bot.send_message(chat_id=message.from_user.id,
                               text="Выберите кнопку:",
                               reply_markup=kb)
    await MainState.admin_settings_bn_set_data.set()


id_bn = None
old_name = None

@dp.message_handler(state=MainState.admin_settings_bn_set_data)
async def settings_bn_public_set_parametr(message: types.Message):
    global id_bn
    global name_public
    global old_name
    name, url = map(str.strip, message.text.split(":", 1))
    cursor.execute(f"SELECT * FROM main_keyboard WHERE title = '{name_public}' AND name = '{name}'")
    row = cursor.fetchall()
    for rows in row:
        id_bn = rows[0]
        old_name = rows[2]
    kb = ReplyKeyboardMarkup()
    kb.add(KeyboardButton('Изменить имя'))
    kb.add(KeyboardButton('Изменить ссылку'))
    await bot.send_message(chat_id=message.from_user.id,
                               text="Выберите опцию:",
                               reply_markup=kb)
    await MainState.admin_settings_bn_set_data_set.set()

parametr = None
@dp.message_handler(Text(equals='Изменить имя'), state=MainState.admin_settings_bn_set_data_set)
async def settings_bn_public_set_parametr_name(message: types.Message):
    global parametr
    parametr = 'name'
    await bot.send_message(chat_id=message.from_user.id,
                               text="Введите новое имя:")
    await MainState.admin_settings_bn_set_data_set_final.set()

@dp.message_handler(Text(equals='Изменить ссылку'), state=MainState.admin_settings_bn_set_data_set)
async def settings_bn_public_set_parametr_url(message: types.Message):
    global parametr
    parametr = 'url'
    await bot.send_message(chat_id=message.from_user.id,
                               text="Введите новую ссылку:")
    await MainState.admin_settings_bn_set_data_set_final.set()

@dp.message_handler(state=MainState.admin_settings_bn_set_data_set_final)
async def settings_bn_public_set_parametr_confirm(message: types.Message):
    global parametr
    global id_bn
    global old_name
    if parametr == 'name':
        cursor.execute(f"UPDATE main_keyboard SET name = ? WHERE id = ? AND name = ?", (message.text, id_bn, old_name))
    elif parametr == 'url':
        cursor.execute(f"UPDATE main_keyboard SET url = ? WHERE id = ? AND name = ?", (message.text, id_bn, old_name))
    con.commit()
    await bot.send_message(chat_id=message.from_user.id,
                               text="Информация обновлена.",
                               reply_markup=kb)
    await MainState.admin_settings.set()

#-Удаление кнопки-
@dp.message_handler(Text(equals='Удалить кнопку'), state=MainState.admin_settings_bn_set)
async def settings_bn_public_del(message: types.Message):
    global name_public
    cursor.execute(f"SELECT * FROM main_keyboard WHERE title = '{name_public}'")
    row = cursor.fetchall()
    kb = ReplyKeyboardMarkup()
    for rows in row:
        kb.add(KeyboardButton(f'{rows[2]}: {rows[3]}'))
    await bot.send_message(chat_id=message.from_user.id,
                               text="Выберите кнопку:",
                               reply_markup=kb)
    await MainState.admin_settings_bn_del.set()

@dp.message_handler(state=MainState.admin_settings_bn_del)
async def settings_bn_public_del_final(message: types.Message):
    global name_public
    name, url = map(str.strip, message.text.split(":", 1))
    cursor.execute(f"DELETE FROM main_keyboard WHERE title = ? AND name = ? AND url = ?", (name_public, name, url))
    con.commit()
    await bot.send_message(chat_id=message.from_user.id,
                               text="Кнопка успешно удалена.",
                               reply_markup=kb)
    await MainState.admin_settings.set()


#-Добавление кнопки-
name = None
url = None
@dp.message_handler(Text(equals='Добавить кнопку'), state=MainState.admin_settings_bn_set)
async def settings_bn_public_add_step1(message: types.Message):
    
    await bot.send_message(chat_id=message.from_user.id,
                               text="Введите имя кнопки:")
    await MainState.admin_settings_bn_set_sp2.set()

@dp.message_handler(state=MainState.admin_settings_bn_set_sp2)
async def settings_bn_public_add_step2(message: types.Message):
    global name
    name = message.text
    await bot.send_message(chat_id=message.from_user.id,
                               text="Введите ссылку для кнопки:")
    await MainState.admin_settings_bn_set_final.set()

@dp.message_handler(state=MainState.admin_settings_bn_set_final)
async def settings_bn_public_add_final(message: types.Message):
    global name_public
    global name
    global url
    url = message.text
    cursor.execute(f"SELECT * FROM main_keyboard WHERE title = '{name_public}'")
    row = cursor.fetchall()
    for rows in row:
        id = rows[0]
    cursor.execute("INSERT INTO main_keyboard (id, title, name, url) VALUES (?, ?, ?, ?)", (id, name_public, name, url))
    con.commit()
    await bot.send_message(chat_id=message.from_user.id,
                               text="Кнопка успешно добавлена.",
                               reply_markup=kb)
    await MainState.admin_settings.set()
    

#-Изменения фотографии-
@dp.message_handler(Text(equals='Изменить фотографию') ,state=MainState.admin_settings)
async def settings_photos(message: types.Message):
    cursor.execute(f"SELECT * FROM main")
    row = cursor.fetchall()
    kb = ReplyKeyboardMarkup()
    for rows in row:
        kb.add(KeyboardButton(f'{rows[1]}'))
    await bot.send_message(chat_id=message.from_user.id,
                               text="Выберите чат:",
                               reply_markup=kb)
    await MainState.admin_settings_photo.set()

name_public = None
@dp.message_handler(state=MainState.admin_settings_photo)
async def settings_photos_public(message: types.Message):
    global name_public
    cursor.execute(f"SELECT * FROM main")
    row = cursor.fetchall()
    for rows in row:
        if message.text == rows[1]:
            name_public = rows[1]
            await bot.send_message(chat_id=message.from_user.id,
                               text=f"Текущее фото для группы {rows[1]}")
            await bot.send_photo(chat_id=message.from_user.id, 
                                 photo=rows[2])
            await bot.send_message(chat_id=message.from_user.id,
                               text="Введите новую ссылку фотографии.")
            await MainState.admin_settings_photo_url.set()

@dp.message_handler(state=MainState.admin_settings_photo_url)
async def settings_messages_public_num(message: types.Message):
    global name_public
    global kb
    cursor.execute(f"UPDATE main SET url = ? WHERE title = ?", (message.text, name_public))
    con.commit()
    await bot.send_message(chat_id=message.from_user.id,
                               text="Данные успешно изменены.",
                               reply_markup=kb)
    await MainState.admin_settings.set()

#-Изменения периодичности-
@dp.message_handler(Text(equals='Изменить периодичность отправки') ,state=MainState.admin_settings)
async def settings_messages(message: types.Message):
    cursor.execute(f"SELECT * FROM number_of_messages")
    row = cursor.fetchall()
    kb = ReplyKeyboardMarkup()
    for rows in row:
        kb.add(KeyboardButton(f'{rows[1]} | количество: {rows[2]}'))
    await bot.send_message(chat_id=message.from_user.id,
                               text="Выберите чат:",
                               reply_markup=kb)
    await MainState.admin_settings_chat.set()

name_public = None
@dp.message_handler(state=MainState.admin_settings_chat)
async def settings_messages_public(message: types.Message):
    global name_public
    cursor.execute(f"SELECT * FROM number_of_messages")
    row = cursor.fetchall()
    for rows in row:
        if message.text.split('|')[0].strip() == f"{rows[1]}":
            name_public = rows[1]
            await bot.send_message(chat_id=message.from_user.id,
                               text="Введите количество сообщений (например: 20).")
            await MainState.admin_settings_chat_number.set()

@dp.message_handler(state=MainState.admin_settings_chat_number)
async def settings_messages_public_num(message: types.Message):
    global name_public
    global kb
    cursor.execute(f"UPDATE number_of_messages SET number = ? WHERE title = ?", (int(message.text), name_public))
    con.commit()
    await bot.send_message(chat_id=message.from_user.id,
                               text="Данные успешно изменены.",
                               reply_markup=kb)
    await MainState.admin_settings.set()
    

# Обработчик всех сообщений
@dp.message_handler()
async def count_messages(message: types.Message):
    chat_id = message.chat.id
    await check_public(message)
    # Получаем число сообщений из базы данных
    num_of_message = get_number_of_messages(message)
    if num_of_message != None:
        # Проверяем, существует ли ключ для данного чата в словаре
        if chat_id not in messages_count:
            messages_count[chat_id] = 1
        else:
            # Увеличиваем счетчик сообщений для данного чата
            messages_count[chat_id] += 1
            
            # Проверяем, достигнуто ли num_of_message сообщений в чате
            if messages_count[chat_id] >= num_of_message:
                await send_notification(chat_id, None, message)
                # Сбрасываем счетчик сообщений для данного чата
                messages_count[chat_id] = 0

@dp.message_handler(commands='cancel' ,state='*')
async def cmd_cancel(message: types.Message):
    await bot.send_message(chat_id=message.from_user.id,
                               text="Вы вернулись в панель администратора.",
                               reply_markup=kb)
    await MainState.admin_settings.set()

if __name__ == '__main__':
    executor.start_polling(dp, on_startup=on_startup, skip_updates=True)
