from aiogram import executor, Dispatcher, types, Bot
from aiogram.utils import exceptions
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import StatesGroup, State
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.dispatcher.filters import Text
import aiogram
import config
import sqlite3
import re

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

#------------ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ-------------
# Словарь для хранения количества отправленных сообщений в каждом чате
messages_history = {}

# Словарь для хранения идентификаторов предыдущих сообщений с фотографией
prev_photo_messages = {}

# Переменные для хранения информации о кнопках
id_bn = None  # Идентификатор кнопки
old_name = None  # Старое название кнопки
name_public = None  # Название публичного чата
parametr = None  # Параметр для изменения кнопки (например, имя или ссылка)
name = None  # Имя новой кнопки
url = None  # Ссылка новой кнопки
#----------------------------------------------


# Создание клавиатуры с вариантами действий
kb = ReplyKeyboardMarkup()

# Добавление кнопок в клавиатуру
kb.add(KeyboardButton("Изменить периодичность отправки"))  # Кнопка для изменения периодичности отправки
kb.add(KeyboardButton("Изменить фотографию | текст"))      # Кнопка для изменения фотографии или текста
kb.add(KeyboardButton("Изменить вариант рекламы"))         # Кнопка для изменения варианта рекламы
kb.add(KeyboardButton("Изменить кнопки"))                  # Кнопка для изменения кнопок
kb.add(KeyboardButton("Предпросмотр"))

# Клавиатура готова к использованию


#---------------МАШИНЫ СОСТОЯНИЙ---------------
# Класс состояний для аутентификации администратора
class MainState(StatesGroup):
    admin_password = State()  # Состояние ожидания ввода пароля администратора
    admin_setting = State()   # Состояние административных настроек

# Класс состояний для изменения контента рекламы
class AdContentModificationState(StatesGroup):
    targetChat = State()  # Состояние ожидания выбора чата
    NewInfo = State()     # Состояние ожидания новой информации

# Класс состояний для изменения клавиатуры
class KeyboardSettingsState(StatesGroup):
    targetChat = State()          # Состояние ожидания выбора чата
    KeyboardSelection = State()   # Состояние ожидания выбора опции изменения клавиатуры
    ButtonChoice = State()        # Состояние ожидания выбора кнопки
    ButtonModification = State()  # Состояние ожидания изменения выбранной кнопки
    ButtonSave = State()          # Состояние ожидания сохранения выбранных параметров для кнопки
    ButtonDeletionSelection = State()  # Состояние ожидания выбора кнопки для удаления
    NewButtonName = State()       # Состояние ожидания ввода имени новой кнопки
    NewButtonLink = State()       # Состояние ожидания ввода ссылки новой кнопки

# Класс состояний для изменения варианта рекламы
class AdVariantState(StatesGroup):
    targetChat = State()  # Состояние ожидания выбора чата

# Класс состояний для изменения периодичности сообщений
class MessageIntervalModificationState(StatesGroup):
    targetChat = State()  # Состояние ожидания выбора чата
    NewInfo = State()     # Состояние ожидания новой информации

class VisionState(StatesGroup):
    vision = State()
#----------------------------------------------


# Обработчик команды отмены в любом состоянии
@dp.message_handler(commands='cancel', state='*')
async def cmd_cancel(message: types.Message):
    """
    Обрабатывает команду отмены в любом состоянии и возвращает пользователя в панель администратора.
    
    :param message: Полученное сообщение с командой отмены
    """
    # Отправляем пользователю сообщение о возвращении в панель администратора
    await bot.send_message(chat_id=message.from_user.id,
                           text="Вы вернулись в панель администратора.",
                           reply_markup=kb)
    
    # Устанавливаем состояние 'admin_settings' для возвращения в панель администратора
    await MainState.admin_setting.set()


# Функция для отправки сообщения оповещения и удаления предыдущего
async def send_notification(chat_id, message_id, message):
    """
    Отправляет сообщение оповещения и удаляет предыдущее, если оно было.
    
    :param chat_id: ID чата, куда отправляется сообщение
    :param message_id: ID предыдущего сообщения, которое нужно удалить
    :param message: Текст сообщения, которое нужно отправить
    """
    try:
        # Удаляем предыдущее сообщение, если оно существует
        if message_id:
            await bot.delete_message(chat_id, message_id)
        
        # Удаляем предыдущее фото-сообщение, если оно существует в словаре prev_photo_messages
        if chat_id in prev_photo_messages:
            await bot.delete_message(chat_id, prev_photo_messages[chat_id])
        
        # Получаем данные для создания клавиатуры из базы данных
        cursor.execute(f"SELECT * FROM main_keyboard WHERE id ={message.chat.id}")
        rows = cursor.fetchall()
        ikb = InlineKeyboardMarkup(resize_keyboard=True)
        for row in rows:
            ikb.add(InlineKeyboardButton(text=row[2], url=row[3]))

        # Получаем данные о главном сообщении из базы данных
        cursor.execute(f"SELECT * FROM main WHERE id ={message.chat.id}")
        row = cursor.fetchone()
        
        # Отправляем сообщение или фото в зависимости от настроек в базе данных
        if row:
            if row[3] == 1:  # Если необходимо отправить фото
                sent_message = await bot.send_photo(chat_id, row[2], reply_markup=ikb)
            else:  # Если необходимо отправить текстовое сообщение
                sent_message = await bot.send_message(chat_id, row[4], reply_markup=ikb)
            
            # Записываем ID нового сообщения в словарь prev_photo_messages
            prev_photo_messages[chat_id] = sent_message.message_id
    except exceptions.MessageToDeleteNotFound:
        pass  # Игнорируем ошибку, если сообщение для удаления не найдено


async def check_public(message: types.Message):
    """
    Проверяет наличие информации о чате в базе данных и добавляет ее, если она отсутствует.
    
    :param message: Сообщение, содержащее информацию о чате
    """
    # Проверяем наличие информации о количестве сообщений в базе данных
    cursor.execute(f"SELECT * FROM number_of_messages WHERE id ={message.chat.id}")
    rows = cursor.fetchall()
    
    if rows == []:
        # Если информация отсутствует, добавляем новую запись
        if str(message.chat.id).startswith('-'):  # Проверяем, является ли ID чата групповым
            cursor.execute("INSERT INTO number_of_messages (id, title, number) VALUES (?, ?, ?)", (message.chat.id, message.chat.title, config.NUMBER_MESSAGE))
            con.commit()
    
    # Проверяем наличие информации о главном сообщении в базе данных
    cursor.execute(f"SELECT * FROM main WHERE id ={message.chat.id}")
    rows = cursor.fetchall()
    
    if rows == []:
        if str(message.chat.id).startswith('-'):  # Проверяем, является ли ID чата групповым
        # Если информация отсутствует, добавляем новую запись
            cursor.execute("INSERT INTO main (id, title, url, status, text) VALUES (?, ?, ?, ?, ?)", (message.chat.id, message.chat.title, config.PHOTO_URL, 1, config.TEXT))
            con.commit()

    # Проверяем наличие информации о клавиатуре в базе данных
    cursor.execute(f"SELECT * FROM main_keyboard WHERE id ={message.chat.id}")
    rows = cursor.fetchall()
    
    if rows == []:
        if str(message.chat.id).startswith('-'):  # Проверяем, является ли ID чата групповым
            # Если информация отсутствует, добавляем новую запись
            cursor.execute("INSERT INTO main_keyboard (id, title, name, url) VALUES (?, ?, ?, ?)", (message.chat.id, message.chat.title, config.BUTTON_NAME, config.BUTTON_URL))
            con.commit()



@dp.message_handler(commands='admin', state='*')
async def cmd_admin(message: types.Message):
    """
    Обработчик команды '/admin', запрашивающий подтверждение прав администратора через ввод пароля.
    
    :param message: Сообщение, содержащее команду '/admin'
    """
    # Отправляем сообщение с запросом пароля для подтверждения прав администратора
    await bot.send_message(chat_id=message.from_user.id,
                           text="Для подтверждения прав введите пароль")
    # Устанавливаем состояние 'admin_check' для ожидания ввода пароля
    await MainState.admin_password.set()


# Обработчик всех сообщений при ожидании проверки администратора
@dp.message_handler(state=MainState.admin_password)
async def admin_password(message: types.Message):
    """
    Проверяет введенный пользователем пароль администратора и предоставляет доступ к настройкам, если пароль верный.
    
    :param message: Сообщение, содержащее введенный пользователем пароль
    """
    global kb  # Глобальная клавиатура, содержащая опции администратора
    if config.ADMIN_PASSWORD == message.text:  # Проверяем правильность введенного пароля
        # Отправляем пользователю сообщение с инструкцией и клавиатурой опций администратора
        await bot.send_message(chat_id=message.from_user.id,
                               text="Выберите опцию:",
                               reply_markup=kb)
        # Устанавливаем состояние 'admin_settings' для настройки администратора
        await MainState.admin_setting.set()
    else:
        # Если пароль неверный, отправляем сообщение об ошибке
        await bot.send_message(chat_id=message.from_user.id,
                               text="Неправильный пароль.")


@dp.message_handler(commands='delete_public', state=MainState.admin_setting)
async def cmd_delete_public(message: types.Message):
    public_name = message.get_args()  # Получаем название паблика из аргументов команды
    if public_name:
        cursor.execute("DELETE FROM main_keyboard WHERE title = ?", (public_name,))
        cursor.execute("DELETE FROM main WHERE title = ?", (public_name,))
        cursor.execute("DELETE FROM number_of_messages WHERE title = ?", (public_name,))
        con.commit()  # Фиксируем изменения в базе данных
        
        # Проверяем количество удаленных строк в таблицах
        if cursor.rowcount > 0:
            await bot.send_message(chat_id=message.from_user.id,
                                   text=f"Вы удалили группу {public_name} из списков.",
                                   reply_markup=kb)
        else:
            await bot.send_message(chat_id=message.from_user.id,
                                   text=f"Группа {public_name} не найдена.",
                                   reply_markup=kb)
    else:
        await bot.send_message(chat_id=message.from_user.id,
                               text=f"Пожалуйста, укажите название паблика после команды /delete_public (Например: /delete_public студенты)",
                               reply_markup=kb)


@dp.message_handler(commands=['delete_message'], state=MainState.admin_setting)
async def delete_message_command(message: types.Message):
    # Получаем текст команды
    command_text = message.get_args()

    # Проверяем, что команда имеет параметры
    if command_text:
        # Проверяем, что команда имеет правильный формат ссылки
        if command_text.startswith('https://t.me/'):
            # Разбиваем текст команды на части по символу '/'
            parts = command_text.split('/')
            # Ожидаем, что идентификатор сообщения находится в последней части разделенной строки
            message_id = parts[-1]
            # Ожидаем, что chat_id находится в предпоследней части разделенной строки и начинается с 'c'
            chat_title = parts[-2]
            
            # Добавляем символ '@' в начало названия чата
            if not chat_title.startswith('@'):
                chat_title = '@' + chat_title
            
            # Получаем числовой идентификатор чата по его имени (title)
            chat = await bot.get_chat(chat_title)
            chat_id = chat.id
            try:

                
                # Удаляем сообщение
                await bot.delete_message(chat_id=chat_id, message_id=message_id)
                await bot.send_message(chat_id=message.from_user.id,
                                       text="Сообщение успешно удалено.")
                return  # Завершаем выполнение функции после удаления сообщения
            except aiogram.utils.exceptions.ChatNotFound:
                await bot.send_message(chat_id=message.from_user.id,
                                       text="Не удалось найти чат.")
                return
        # Если формат ссылки некорректный, отправляем сообщение об ошибке
        await bot.send_message(chat_id=message.from_user.id,
                               text="Некорректный формат ссылки на сообщение. Пожалуйста, укажите правильную ссылку.")
    else:
        await bot.send_message(chat_id=message.from_user.id,
                               text="Пожалуйста, укажите ссылку на сообщение после команды '/delete_message'.")


# print(chat_id, message_id)




@dp.message_handler(Text(equals='Предпросмотр'), state=MainState.admin_setting)
async def settings_vision(message: types.Message):
    """
    Обрабатывает запрос на изменение варианта рекламы и предоставляет список доступных чатов для выбора.
    
    :param message: Сообщение с запросом на изменение варианта рекламы
    """
    # Получаем список уникальных названий чатов из базы данных
    cursor.execute("SELECT DISTINCT title FROM main")
    unique_rows = cursor.fetchall()
    
    if unique_rows:  # Проверяем, не пуст ли список уникальных названий чатов
        # Создаем клавиатуру для выбора чата и добавляем кнопки с уникальными названиями чатов
        kb = ReplyKeyboardMarkup()
        for row in unique_rows:
            kb.add(KeyboardButton(f'{row[0]}'))
        
        # Отправляем сообщение с просьбой выбрать чат и клавиатурой
        await bot.send_message(chat_id=message.from_user.id,
                               text="Выберите чат:",
                               reply_markup=kb)
        # Устанавливаем состояние 'targetChat' для ожидания выбора чата
        await VisionState.vision.set()
    else:
        await bot.send_message(chat_id=message.from_user.id,
                               text="Группы не найдены.")
        
# Обработчик для изменения статуса варианта рекламы выбранного чата
@dp.message_handler(state=VisionState.vision)
async def settings_vision_confirm(message: types.Message):
    cursor.execute(f"SELECT * FROM main WHERE title = '{message.text}'")
    row = cursor.fetchall()
    for rows in row:
        chat_id = rows[0]
    # Получаем данные для создания клавиатуры из базы данных
    cursor.execute(f"SELECT * FROM main_keyboard WHERE id ={chat_id}")
    rows = cursor.fetchall()
    ikb = InlineKeyboardMarkup(resize_keyboard=True)
    for row in rows:
        ikb.add(InlineKeyboardButton(text=row[2], url=row[3]))
    # print(chat_id, )
    # Получаем данные о главном сообщении из базы данных
    cursor.execute(f"SELECT * FROM main WHERE id ={chat_id}")
    row = cursor.fetchone()
    await bot.send_message(chat_id=message.from_user.id,
                                   text=f'Предпросмотр рекламы для группы {message.text}',
                                   reply_markup=kb)
    # Отправляем сообщение или фото в зависимости от настроек в базе данных
    if row:
        if row[3] == 1:  # Если необходимо отправить фото
            await bot.send_photo(chat_id=message.from_user.id,
                                photo=row[2], 
                                reply_markup=ikb)
        else:  # Если необходимо отправить текстовое сообщение
            await bot.send_message(chat_id=message.from_user.id,
                                   text=row[4],
                                   reply_markup=ikb)
    await bot.send_message(chat_id=message.from_user.id,
                                   text='Вы вернулись в панель администратора.',
                                   reply_markup=kb)
    # Устанавливаем состояние 'admin_setting' для завершения процесса изменения настроек администратора
    await MainState.admin_setting.set()
    

#----------ИЗМЕНЕНИЯ ВАРИАНТА РЕКЛАМЫ----------
@dp.message_handler(Text(equals='Изменить вариант рекламы'), state=MainState.admin_setting)
async def settings_status(message: types.Message):
    """
    Обрабатывает запрос на изменение варианта рекламы и предоставляет список доступных чатов для выбора.
    
    :param message: Сообщение с запросом на изменение варианта рекламы
    """
    # Получаем список уникальных названий чатов из базы данных
    cursor.execute("SELECT DISTINCT title FROM main")
    unique_rows = cursor.fetchall()
    
    if unique_rows:  # Проверяем, не пуст ли список уникальных названий чатов
        # Создаем клавиатуру для выбора чата и добавляем кнопки с уникальными названиями чатов
        kb = ReplyKeyboardMarkup()
        for row in unique_rows:
            kb.add(KeyboardButton(f'{row[0]}'))
        
        # Отправляем сообщение с просьбой выбрать чат и клавиатурой
        await bot.send_message(chat_id=message.from_user.id,
                               text="Выберите чат:",
                               reply_markup=kb)
        # Устанавливаем состояние 'targetChat' для ожидания выбора чата
        await AdVariantState.targetChat.set()
    else:
        await bot.send_message(chat_id=message.from_user.id,
                               text="Группы не найдены.")


# Обработчик для изменения статуса варианта рекламы выбранного чата
@dp.message_handler(state=AdVariantState.targetChat)
async def settings_status_confirm(message: types.Message):
    """
    Обрабатывает выбор чата и изменяет его статус варианта рекламы.
    
    :param message: Сообщение с выбранным чатом
    """
    global name_public  # Глобальная переменная с названием чата
    cursor.execute(f"SELECT * FROM main WHERE title = '{message.text}'")  # Извлекаем информацию о выбранном чате из базы данных
    row = cursor.fetchall()
    for rows in row:
        if rows[3] == 1:  # Если текущий статус рекламы - активен
            cursor.execute(f"UPDATE main SET status = ? WHERE title = ?", (2, message.text))  # Меняем статус на неактивен
            # Отправляем сообщение о успешном изменении варианта рекламы
            await bot.send_message(chat_id=message.from_user.id,
                                text="Вариант изменён на текст.",
                                reply_markup=kb)
        elif rows[3] == 2:  # Если текущий статус рекламы - неактивен
            cursor.execute(f"UPDATE main SET status = ? WHERE title = ?", (1, message.text))  # Меняем статус на активен
            # Отправляем сообщение о успешном изменении варианта рекламы
            await bot.send_message(chat_id=message.from_user.id,
                                text="Вариант изменён на фотографию.",
                                reply_markup=kb)
        con.commit()  # Фиксируем изменения в базе данных
    # Устанавливаем состояние 'admin_setting' для завершения процесса изменения настроек администратора
    await MainState.admin_setting.set()
#----------------------------------------------


#-------------ИЗМЕНЕНИЯ КЛАВИАТУРЫ-------------
@dp.message_handler(Text(equals='Изменить кнопки'), state=MainState.admin_setting)
async def settings_bn(message: types.Message):
    """
    Обрабатывает запрос на изменение кнопок в клавиатуре и предоставляет список доступных чатов для выбора.
    
    :param message: Сообщение с запросом на изменение кнопок в клавиатуре
    """
    # Получаем список уникальных названий чатов из базы данных, содержащих кнопки
    cursor.execute("SELECT DISTINCT title FROM main")
    unique_rows = cursor.fetchall()
    
    if unique_rows:  # Проверяем, не пуст ли список уникальных названий чатов
        # Создаем клавиатуру для выбора чата и добавляем кнопки с уникальными названиями чатов
        kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        for row in unique_rows:
            kb.add(KeyboardButton(f'{row[0]}'))
        
        # Отправляем сообщение с просьбой выбрать чат и клавиатурой
        await bot.send_message(chat_id=message.from_user.id,
                               text="Выберите чат:",
                               reply_markup=kb)
        
        # Устанавливаем состояние 'targetChat' для ожидания выбора чата
        await KeyboardSettingsState.targetChat.set()
    else:
        await bot.send_message(chat_id=message.from_user.id,
                               text="Нет доступных чатов для изменения кнопок.")



# Обработчик для установки настроек кнопок выбранного чата
@dp.message_handler(state=KeyboardSettingsState.targetChat)
async def settings_bn_public(message: types.Message):
    """
    Устанавливает настройки кнопок для выбранного чата.
    
    :param message: Сообщение с выбранным чатом
    """
    global name_public  # Глобальная переменная с названием чата
    cursor.execute(f"SELECT * FROM main_keyboard")  # Получаем информацию о кнопках из базы данных
    row = cursor.fetchall()
    name_public = message.text  # Получаем название выбранного чата
    # Отправляем сообщение с названием выбранного чата
    await bot.send_message(chat_id=message.from_user.id,
                           text=f"Для группы {name_public} бот имеет следующие кнопки:")
    for rows in row:
        if message.text == rows[1]:  # Если название чата соответствует выбранному
            name_public = rows[1]
            # Отправляем информацию о кнопках в выбранном чате
            await bot.send_message(chat_id=message.from_user.id,
                                   text=f"Название кнопки: {rows[2]}\nСодержание: {rows[3]}")
    # Создаем клавиатуру с опциями для управления кнопками
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(KeyboardButton("Добавить кнопку"))
    kb.insert(KeyboardButton("Удалить кнопку"))
    kb.add(KeyboardButton("Изменить кнопку"))
    # Отправляем сообщение с просьбой выбрать опцию и клавиатурой
    await bot.send_message(chat_id=message.from_user.id,
                           text="Выберите опцию:",
                           reply_markup=kb)
    # Устанавливаем состояние 'KeyboardSelection' для ожидания выбора опции
    await KeyboardSettingsState.KeyboardSelection.set()


# Обработчик для изменения кнопки в выбранном чате
@dp.message_handler(Text(equals='Изменить кнопку'), state=KeyboardSettingsState.KeyboardSelection)
async def settings_bn_choice(message: types.Message):
    """
    Обрабатывает запрос на изменение кнопки в выбранном чате и предоставляет список доступных кнопок для выбора.
    
    :param message: Сообщение с запросом на изменение кнопки
    """
    global name_public  # Глобальная переменная с названием чата
    cursor.execute(f"SELECT * FROM main_keyboard WHERE title = '{name_public}'")  # Получаем информацию о кнопках выбранного чата из базы данных
    row = cursor.fetchall()
    
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)  # Создаем клавиатуру для выбора кнопок
    i = 1
    for rows in row:
        if i == 1:
            kb.add(KeyboardButton(f'Кнопка: {rows[2]}'))  # Добавляем кнопки в клавиатуру
            i += 1
        elif i == 2:
            kb.insert(KeyboardButton(f'Кнопка: {rows[2]}'))  # Добавляем кнопки в клавиатуру
            i = 1
    
    # Отправляем сообщение с просьбой выбрать кнопку и клавиатурой
    await bot.send_message(chat_id=message.from_user.id,
                           text="Выберите кнопку:",
                           reply_markup=kb)
    
    # Устанавливаем состояние 'ButtonChoice' для ожидания выбора кнопки
    await KeyboardSettingsState.ButtonChoice.set()


# Обработчик для установки параметров выбранной кнопки
@dp.message_handler(state=KeyboardSettingsState.ButtonChoice)
async def settings_bn_enter_option(message: types.Message):
    """
    Обрабатывает установку параметров выбранной кнопки и предоставляет опции для изменения параметров.
    
    :param message: Сообщение с выбранной кнопкой и параметрами
    """
    global id_bn  # Глобальная переменная для идентификатора кнопки
    global name_public  # Глобальная переменная с названием чата
    global old_name  # Глобальная переменная с текущим названием кнопки
    
    # Получаем имя и ссылку выбранной кнопки из сообщения
    name = message.text.split(':')[1].strip()

    
    # Получаем информацию о выбранной кнопке из базы данных
    cursor.execute(f"SELECT * FROM main_keyboard WHERE title = '{name_public}' AND name = '{name}'")
    row = cursor.fetchall()
    
    for rows in row:
        id_bn = rows[0]  # Сохраняем идентификатор выбранной кнопки
        old_name = rows[2]  # Сохраняем текущее название кнопки
    
    # Создаем клавиатуру с опциями для изменения параметров кнопки
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(KeyboardButton('Изменить имя'))
    kb.insert(KeyboardButton('Изменить ссылку'))
    
    # Отправляем сообщение с просьбой выбрать опцию и клавиатурой
    await bot.send_message(chat_id=message.from_user.id,
                           text="Выберите опцию:",
                           reply_markup=kb)
    
    # Устанавливаем состояние 'ButtonModification' для ожидания выбора опции
    await KeyboardSettingsState.ButtonModification.set()


# Обработчик для изменения имени выбранной кнопки
@dp.message_handler(Text(equals='Изменить имя'), state=KeyboardSettingsState.ButtonModification)
async def settings_bn_option_name(message: types.Message):
    """
    Обрабатывает запрос на изменение имени выбранной кнопки и ожидает ввода нового имени.
    
    :param message: Сообщение с запросом на изменение имени кнопки
    """
    global parametr  # Глобальная переменная для хранения параметра, который будет изменен
    parametr = 'name'  # Устанавливаем параметр 'name' для изменения имени кнопки
    
    # Отправляем сообщение с просьбой ввести новое имя кнопки
    await bot.send_message(chat_id=message.from_user.id,
                           text="Введите новое имя:")
    
    # Устанавливаем состояние 'admin_settings_bn_set_data_set_final' для ожидания ввода нового имени
    await KeyboardSettingsState.ButtonSave.set()


# Обработчик для изменения ссылки выбранной кнопки
@dp.message_handler(Text(equals='Изменить ссылку'), state=KeyboardSettingsState.ButtonModification)
async def settings_bn_option_url(message: types.Message):
    """
    Обрабатывает запрос на изменение ссылки выбранной кнопки и ожидает ввода новой ссылки.
    
    :param message: Сообщение с запросом на изменение ссылки кнопки
    """
    global parametr  # Глобальная переменная для хранения параметра, который будет изменен
    parametr = 'url'  # Устанавливаем параметр 'url' для изменения ссылки кнопки
    
    # Отправляем сообщение с просьбой ввести новую ссылку кнопки
    await bot.send_message(chat_id=message.from_user.id,
                           text="Введите новую ссылку:")
    
    # Устанавливаем состояние 'admin_settings_bn_set_data_set_final' для ожидания ввода новой ссылки
    await KeyboardSettingsState.ButtonSave.set()


from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.exceptions import InvalidHTTPUrlContent, BadRequest

@dp.message_handler(state=KeyboardSettingsState.ButtonSave)
async def settings_bn_save(message: types.Message):
    """
    Обрабатывает подтверждение изменения параметра выбранной кнопки и обновляет информацию в базе данных.
    
    :param message: Сообщение с подтверждением изменения параметра
    """
    global parametr  # Глобальная переменная для хранения параметра, который будет изменен
    global id_bn  # Глобальная переменная для идентификатора кнопки
    global old_name  # Глобальная переменная с текущим названием кнопки
    
    # Проверяем, какой параметр был изменен
    if parametr == 'name':  # Если изменялось имя кнопки
        # Обновляем информацию о имени кнопки в базе данных
        cursor.execute(f"UPDATE main_keyboard SET name = ? WHERE id = ? AND name = ?", (message.text, id_bn, old_name))
    elif parametr == 'url':  # Если изменялась ссылка кнопки
        # Создаем инлайн-кнопку для проверки ссылки
        if message.text.startswith("@"):
            # https://t.me/@reklama_horizont
            url=f"https://t.me/{message.text[1:]}"
        else:
            url=message.text
        url_button = InlineKeyboardButton(text="Проверить ссылку", url=url)
        keyboard = InlineKeyboardMarkup().add(url_button)
        
        try:
            # Проверяем, доступна ли ссылка
            await bot.send_message(message.chat.id, "Проверка ссылки...", reply_markup=keyboard)
        except (InvalidHTTPUrlContent, BadRequest):
            await message.reply("Некорректная ссылка. Пожалуйста, введите корректную ссылку или username.",reply_markup=kb)
            # Устанавливаем состояние 'admin_setting' для завершения процесса изменения настроек администратора
            await MainState.admin_setting.set()
            return
    
        # Если ссылка прошла проверку, обновляем информацию о ссылке кнопки в базе данных
        cursor.execute(f"UPDATE main_keyboard SET url = ? WHERE id = ? AND name = ?", (url, id_bn, old_name))
    
    con.commit()  # Фиксируем изменения в базе данных
    
    # Отправляем сообщение об успешном удалении кнопки
    await bot.send_message(chat_id=message.from_user.id,
                           text="Информация обновлена.",
                           reply_markup=kb)
    
    # Устанавливаем состояние 'admin_setting' для завершения процесса изменения настроек администратора
    await MainState.admin_setting.set()

#----------------------------------------------


#---------------УДАЛЕНИЕ КНОПКИ----------------
# Обработчик для удаления кнопки в выбранном чате
@dp.message_handler(Text(equals='Удалить кнопку'), state=KeyboardSettingsState.KeyboardSelection)
async def settings_bn_option_del(message: types.Message):
    """
    Обрабатывает запрос на удаление кнопки в выбранном чате и предоставляет список доступных кнопок для выбора.
    
    :param message: Сообщение с запросом на удаление кнопки
    """
    global name_public  # Глобальная переменная с названием чата
    cursor.execute(f"SELECT * FROM main_keyboard WHERE title = '{name_public}'")  # Получаем информацию о кнопках выбранного чата из базы данных
    row = cursor.fetchall()
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)  # Создаем клавиатуру для выбора кнопок
    i = 1
    for rows in row:
        if i == 1:
            kb.add(KeyboardButton(f'Кнопка: {rows[2]}'))  # Добавляем кнопки в клавиатуру
            i += 1
        elif i == 2:
            kb.insert(KeyboardButton(f'Кнопка: {rows[2]}'))  # Добавляем кнопки в клавиатуру
            i = 1
    
    # Отправляем сообщение с просьбой выбрать кнопку и клавиатурой
    await bot.send_message(chat_id=message.from_user.id,
                           text="Выберите кнопку:",
                           reply_markup=kb)
    
    # Устанавливаем состояние 'ButtonDeletionSelection' для ожидания выбора кнопки для удаления
    await KeyboardSettingsState.ButtonDeletionSelection.set()


# Обработчик для подтверждения удаления выбранной кнопки
@dp.message_handler(state=KeyboardSettingsState.ButtonDeletionSelection)
async def settings_bn_del_confirm(message: types.Message):
    """
    Обрабатывает подтверждение удаления выбранной кнопки и удаляет информацию о ней из базы данных.
    
    :param message: Сообщение с подтверждением удаления кнопки
    """
    global name_public  # Глобальная переменная с названием чата
    
    # Получаем имя и выбранной кнопки из сообщения
    name = message.text.split(':')[1].strip()
    
    # Проверяем, сколько кнопок осталось у данного чата
    cursor.execute("SELECT COUNT(*) FROM main_keyboard WHERE title = ?", (name_public,))
    num_buttons = cursor.fetchone()[0]
    
    if num_buttons == 1:
        # Если осталась только одна кнопка, выводим сообщение об ошибке и завершаем функцию
        await bot.send_message(chat_id=message.from_user.id,
                               text="Невозможно удалить последнюю кнопку.",
                               reply_markup=kb)
        # Устанавливаем состояние 'admin_setting' для завершения процесса изменения настроек администратора
        await MainState.admin_setting.set()
        return
    
    # Удаляем информацию о выбранной кнопке из базы данных
    cursor.execute(f"DELETE FROM main_keyboard WHERE title = ? AND name = ?", (name_public, name))
    con.commit()  # Фиксируем изменения в базе данных
    
    # Отправляем сообщение об успешном удалении кнопки
    await bot.send_message(chat_id=message.from_user.id,
                           text="Кнопка успешно удалена.",
                           reply_markup=kb)
    
    # Устанавливаем состояние 'admin_setting' для завершения процесса изменения настроек администратора
    await MainState.admin_setting.set()

#----------------------------------------------


#--------------ДОБАВЛЕНИЕ КНОПКИ---------------
# Обработчик для добавления новой кнопки в выбранный чат
@dp.message_handler(Text(equals='Добавить кнопку'), state=KeyboardSettingsState.KeyboardSelection)
async def settings_bn_new_name(message: types.Message):
    """
    Обрабатывает запрос на добавление новой кнопки в выбранный чат и ожидает ввода имени новой кнопки.
    
    :param message: Сообщение с запросом на добавление новой кнопки
    """
    # Отправляем сообщение с просьбой ввести имя новой кнопки
    await bot.send_message(chat_id=message.from_user.id,
                           text="Введите имя кнопки:")
    
    # Устанавливаем состояние 'NewButtonName' для ожидания ввода имени новой кнопки
    await KeyboardSettingsState.NewButtonName.set()


# Обработчик для добавления новой кнопки в выбранный чат (шаг 2)
@dp.message_handler(state=KeyboardSettingsState.NewButtonName)
async def settings_bn_new_link(message: types.Message):
    """
    Обрабатывает ввод имени новой кнопки и предлагает ввести ссылку для новой кнопки.
    
    :param message: Сообщение с введенным именем новой кнопки
    """
    global name  # Глобальная переменная для хранения имени новой кнопки
    name = message.text  # Сохраняем введенное имя новой кнопки
    
    # Отправляем сообщение с просьбой ввести ссылку для новой кнопки
    await bot.send_message(chat_id=message.from_user.id,
                           text="Введите ссылку для кнопки:")
    
    # Устанавливаем состояние 'NewButtonLink' для ожидания ввода ссылки для новой кнопки
    await KeyboardSettingsState.NewButtonLink.set()


from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.exceptions import InvalidHTTPUrlContent, BadRequest

@dp.message_handler(state=KeyboardSettingsState.NewButtonLink)
async def settings_bn_add(message: types.Message):
    """
    Обрабатывает завершение добавления новой кнопки в выбранный чат и добавляет информацию о ней в базу данных.
    
    :param message: Сообщение с ссылкой для новой кнопки
    """
    global name_public  # Глобальная переменная с названием чата
    global name  # Глобальная переменная с именем новой кнопки
    global url  # Глобальная переменная с ссылкой для новой кнопки
    
    url = message.text  # Сохраняем введенную ссылку для новой кнопки
    
    # Получаем информацию о кнопках выбранного чата из базы данных
    cursor.execute(f"SELECT * FROM main_keyboard WHERE title = '{name_public}'")
    row = cursor.fetchall()
    
    for rows in row:
        id = rows[0]  # Получаем идентификатор чата для добавления новой кнопки
    
    if url.startswith("@"):
        # https://t.me/@reklama_horizont
        url=f"https://t.me/{message.text[1:]}"
    
    # Создаем инлайн-кнопку для проверки ссылки
    url_button = InlineKeyboardButton(text="Проверить ссылку", url=url)
    keyboard = InlineKeyboardMarkup().add(url_button)

    
    try:
        # Проверяем, доступна ли ссылка
        await bot.send_message(message.chat.id, "Проверка ссылки...", reply_markup=keyboard)
    except (InvalidHTTPUrlContent, BadRequest):
        await message.reply("Некорректная ссылка. Пожалуйста, введите корректную ссылку или username.",reply_markup=kb)
        # Устанавливаем состояние 'admin_settings' для завершения процесса изменения настроек администратора
        await MainState.admin_setting.set()
        return
    
    # Если ссылка прошла проверку, добавляем информацию о новой кнопке в базу данных
    cursor.execute("INSERT INTO main_keyboard (id, title, name, url) VALUES (?, ?, ?, ?)", (id, name_public, name, url))
    con.commit()  # Фиксируем изменения в базе данных
    
    # Отправляем сообщение об успешном добавлении новой кнопки
    await message.reply("Кнопка успешно добавлена.", reply_markup=kb)
    
    # Устанавливаем состояние 'admin_settings' для завершения процесса изменения настроек администратора
    await MainState.admin_setting.set()

#----------------------------------------------


#-----------ИЗМЕНЕНИЕ ФОТО | ТЕКСТА------------
@dp.message_handler(Text(equals='Изменить фотографию | текст'), state=MainState.admin_setting)
async def settings_data(message: types.Message):
    """
    Обрабатывает запрос на изменение фотографии или текста в выбранном чате и предоставляет список доступных чатов для выбора.
    
    :param message: Сообщение с запросом на изменение фотографии или текста
    """
    # Асинхронно получаем список чатов из базы данных
    cursor.execute("SELECT * FROM main")
    rows = cursor.fetchall()
    
    if rows:  # Проверяем, не пуст ли список чатов
        # Создаем клавиатуру для выбора чата
        kb = ReplyKeyboardMarkup()
        for row in rows:
            kb.add(KeyboardButton(row[1]))
        
        # Отправляем сообщение с просьбой выбрать чат и клавиатурой
        await bot.send_message(chat_id=message.from_user.id,
                               text="Выберите чат:",
                               reply_markup=kb)
        
        # Устанавливаем состояние 'targetChat' для ожидания выбора чата для изменения фотографии или текста
        await AdContentModificationState.targetChat.set()
    else:
        await bot.send_message(chat_id=message.from_user.id,
                               text="Нет доступных чатов для изменения фотографии или текста.")



# Обработчик для выбора чата и определения типа изменения (фотография или текст)
@dp.message_handler(state=AdContentModificationState.targetChat)
async def settings_option_types(message: types.Message):
    """
    Обрабатывает выбор чата и определение типа изменения (фотография или текст) и предоставляет инструкции для ввода новой информации.
    
    :param message: Сообщение с выбранным чатом для изменения информации
    """
    global name_public  # Глобальная переменная с названием чата
    
    # Получаем список чатов из базы данных
    cursor.execute(f"SELECT * FROM main")
    row = cursor.fetchall()
    
    for rows in row:
        if message.text == rows[1]:  # Если выбранное название чата соответствует одному из чатов в базе данных
            name_public = rows[1]  # Сохраняем название выбранного чата
            
            if rows[3] == 1:  # Если тип чата - фотография
                # Отправляем сообщение с текущей фотографией и просьбой ввести новую ссылку для фотографии
                await bot.send_message(chat_id=message.from_user.id,
                                       text=f"Текущее фото для группы {rows[1]}")
                await bot.send_photo(chat_id=message.from_user.id, 
                                     photo=rows[2])
                await bot.send_message(chat_id=message.from_user.id,
                                       text="Введите новую ссылку фотографии.")
            elif rows[3] == 2:  # Если тип чата - текст
                # Отправляем сообщение с текущим текстом и просьбой ввести новый текст
                await bot.send_message(chat_id=message.from_user.id,
                                       text=f"Текущий текст для группы {rows[1]}")
                await bot.send_message(chat_id=message.from_user.id, 
                                       text=rows[4])
                await bot.send_message(chat_id=message.from_user.id,
                                       text="Введите новый текст.")
            
            # Устанавливаем состояние 'NewInfo' для ожидания ввода новой информации (ссылки на фотографию или нового текста)
            await AdContentModificationState.NewInfo.set()
            break


@dp.message_handler(state=AdContentModificationState.NewInfo)
async def settings_confirm_data(message: types.Message, state: FSMContext):
    """
    Обрабатывает ввод новой информации (ссылки на фотографию или нового текста) и завершение изменения в выбранном чате.
    
    :param message: Сообщение с введенной новой информацией
    :param state: Состояние FSM
    """
    global name_public  # Глобальная переменная с названием чата
    global kb  # Глобальная переменная с клавиатурой
    
    # Регулярное выражение для поиска ссылок
    regular = r'https?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    # Поиск ссылок в строке
    url = re.findall(regular, message.text)
    
    if url:  # Если найдена ссылка
        # Проверка, является ли ссылка действительной
        try:
            # Попытка отправить фотографию по найденной ссылке
            await bot.send_photo(message.chat.id, url[0])
        except Exception as e:
            # В случае ошибки отправки фотографии выводим сообщение о некорректной ссылке и завершаем функцию
            await bot.send_message(chat_id=message.from_user.id,
                           text="Некорректная ссылка на фотографию. Пожалуйста, проверьте ссылку.")
            await bot.send_message(chat_id=message.from_user.id,
                           text="Вы вернулись в панель администратора.",
                           reply_markup=kb)
            await MainState.admin_setting.set()
            return
        # Если фотография была успешно отправлена, обновляем информацию о чате в базе данных
        cursor.execute("UPDATE main SET text = ?, url = ? WHERE title = ? AND status = ?", (message.text, url[0], name_public, 2))
    else:
        # В случае отсутствия ссылки в сообщении, просто обновляем текст
        cursor.execute("UPDATE main SET text = ? WHERE title = ? AND status = ?", (message.text, name_public, 2))
        
    con.commit()
    
    # Отправляем сообщение об успешном изменении данных
    await bot.send_message(chat_id=message.from_user.id,
                           text="Данные успешно изменены.",
                           reply_markup=kb)
    
    # Устанавливаем состояние 'admin_settings' для завершения процесса изменения настроек администратора
    await MainState.admin_setting.set()

#----------------------------------------------


#-----------ИЗМЕНЕНИЕ ПЕРИОДИЧНОСТИ------------
@dp.message_handler(Text(equals='Изменить периодичность отправки'), state=MainState.admin_setting)
async def settings_interval(message: types.Message):
    """
    Обрабатывает запрос на изменение периодичности отправки сообщений в выбранном чате и предоставляет список доступных чатов для выбора.
    
    :param message: Сообщение с запросом на изменение периодичности отправки сообщений
    """
    # Асинхронно получаем список чатов из базы данных
    cursor.execute("SELECT * FROM number_of_messages")
    rows = cursor.fetchall()
    
    if rows:  # Проверяем, не пуст ли список чатов
        # Создаем клавиатуру для выбора чата
        kb = ReplyKeyboardMarkup()
        for row in rows:
            kb.add(KeyboardButton(f'{row[1]} ; количество: {row[2]}'))
        
        # Отправляем сообщение с просьбой выбрать чат и клавиатурой
        await bot.send_message(chat_id=message.from_user.id,
                               text="Выберите чат:",
                               reply_markup=kb)
        
        # Устанавливаем состояние 'targetChat' для ожидания выбора чата для изменения периодичности отправки сообщений
        await MessageIntervalModificationState.targetChat.set()
    else:
        await bot.send_message(chat_id=message.from_user.id,
                               text="Нет доступных чатов для изменения периодичности отправки сообщений.")



# Обработчик для выбора чата и установки нового значения периодичности отправки сообщений
@dp.message_handler(state=MessageIntervalModificationState.targetChat)
async def settings_new_interval(message: types.Message):
    """
    Обрабатывает выбор чата и устанавливает новое значение периодичности отправки сообщений в выбранном чате.
    
    :param message: Сообщение с выбранным чатом и новым значением периодичности отправки сообщений
    """
    global name_public  # Глобальная переменная с названием чата
    
    # Получаем список чатов и их текущей периодичности отправки сообщений из базы данных
    cursor.execute(f"SELECT * FROM number_of_messages")
    row = cursor.fetchall()
    
    for rows in row:
        if message.text.split(';')[0].strip() == f"{rows[1]}":  # Если выбранный чат соответствует одному из чатов в базе данных
            name_public = rows[1]  # Сохраняем название выбранного чата
            
            # Отправляем сообщение с просьбой ввести новое количество сообщений
            await bot.send_message(chat_id=message.from_user.id,
                                   text="Введите количество сообщений (например: 20).")
            
            # Устанавливаем состояние 'NewInfo' для ожидания ввода нового количества сообщений
            await MessageIntervalModificationState.NewInfo.set()
            break


# Обработчик для установки нового значения периодичности отправки сообщений в выбранном чате
@dp.message_handler(state=MessageIntervalModificationState.NewInfo)
async def settings_interval_confirm(message: types.Message):
    """
    Обрабатывает установку нового значения периодичности отправки сообщений в выбранном чате и завершение процесса изменения.
    
    :param message: Сообщение с новым значением периодичности отправки сообщений
    """
    global name_public  # Глобальная переменная с названием чата
    global kb  # Глобальная переменная с клавиатурой
    
    # Обновляем значение периодичности отправки сообщений для выбранного чата в базе данных
    cursor.execute(f"UPDATE number_of_messages SET number = ? WHERE title = ?", (int(message.text), name_public))
    con.commit()
    
    # Отправляем сообщение об успешном изменении данных
    await bot.send_message(chat_id=message.from_user.id,
                           text="Данные успешно изменены.",
                           reply_markup=kb)
    
    # Устанавливаем состояние 'admin_settings' для завершения процесса изменения настроек администратора
    await MainState.admin_setting.set()
#----------------------------------------------

# Обработчик всех сообщений
@dp.message_handler()
async def count_messages(message: types.Message):
    """
    Обрабатывает все сообщения и ведет подсчет отправленных сообщений в каждом чате. 
    При достижении определенного числа сообщений в чате, отправляет оповещение и сбрасывает счетчик.
    
    :param message: Полученное сообщение
    """
    
    global messages_history
    chat_id = message.chat.id  # ID чата
    await check_public(message)  # Проверка, публичный ли чат
    num_of_message = get_number_of_messages(message)  # Получаем число сообщений из базы данных
    
    # Инкрементируем счетчик сообщений в истории
    if chat_id not in messages_history:
        messages_history[chat_id] = 1
    else:
        messages_history[chat_id] += 1
    
    # Проверяем, достигнуто ли num_of_message сообщений в чате
    if num_of_message is not None and messages_history[chat_id] >= num_of_message:
        await send_notification(chat_id, None, message)  # Отправляем оповещение
        messages_history[chat_id] = 0  # Сбрасываем счетчик сообщений для данного чата



if __name__ == '__main__':
    executor.start_polling(dp, on_startup=on_startup, skip_updates=True)
