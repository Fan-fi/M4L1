from telebot import TeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from logic import *
import schedule
import threading
import time
from config import *

bot = TeleBot(API_TOKEN)

def gen_markup(id):
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(InlineKeyboardButton("Получить!", callback_data=id))
    return markup

# ===== ДОБАВЛЯЕМ НОВЫЕ КНОПКИ =====
def gen_retry_markup(prize_id):
    """Клавиатура для повторного получения"""
    markup = InlineKeyboardMarkup()
    markup.row_width = 2
    markup.add(
        InlineKeyboardButton("🎁 Получить сейчас", callback_data=f"retry_get_{prize_id}"),
        InlineKeyboardButton("⏰ Получить позже", callback_data=f"retry_later_{prize_id}")
    )
    return markup

def gen_admin_markup():
    """Клавиатура для админ-панели"""
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(
        InlineKeyboardButton("🔄 Отправить повторно", callback_data="admin_retry"),
        InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")
    )
    return markup
# ===== КОНЕЦ НОВЫХ КНОПОК =====

# ===== СУЩЕСТВУЮЩИЙ КОД БЕЗ ИЗМЕНЕНИЙ =====
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    prize_id = call.data
    user_id = call.message.chat.id

    img = manager.get_prize_img(prize_id)
    with open(f'img/{img}', 'rb') as photo:
        bot.send_photo(user_id, photo)


def send_message():
    prize_id, img = manager.get_random_prize()[:2]
    manager.mark_prize_used(prize_id)
    hide_img(img)
    for user in manager.get_users():
        with open(f'hidden_img/{img}', 'rb') as photo:
            bot.send_photo(user, photo, reply_markup=gen_markup(id = prize_id))
# ===== КОНЕЦ СУЩЕСТВУЮЩЕГО КОДА =====

# ===== ДОБАВЛЯЕМ НОВЫЕ КОМАНДЫ =====
@bot.message_handler(commands=['retry'])
def handle_retry(message):
    """Показать доступные для повторного получения призы"""
    user_id = message.from_user.id
    
    # Получаем призы, которые можно отправить повторно
    expired_prizes = manager.get_expired_prizes()
    
    if expired_prizes:
        text = "🔄 *Доступные для повторного получения призы:*\n\n"
        for prize_id, img_name, winners_count in expired_prizes[:5]:  # Показываем первые 5
            text += f"🎁 Приз #{prize_id}\n"
            text += f"👥 Победителей: {winners_count}/3\n"
            text += f"🔄 Можно получить: {'Да' if manager.can_get_prize_retry(prize_id, user_id) else 'Нет'}\n\n"
        
        # Показываем кнопку для первого доступного приза
        for prize_id, img_name, winners_count in expired_prizes:
            if manager.can_get_prize_retry(prize_id, user_id):
                bot.send_message(user_id, text, parse_mode='Markdown', reply_markup=gen_retry_markup(prize_id))
                return
        
        bot.send_message(user_id, "😔 Ты уже получал все доступные призы")
    else:
        bot.send_message(user_id, "🎉 Пока нет призов для повторного получения")

@bot.message_handler(commands=['admin'])
def handle_admin(message):
    """Админ-панель для управления повторной отправкой"""
    # Проверяем, является ли пользователь админом (можно добавить проверку)
    user_id = message.from_user.id
    # if user_id not in ADMIN_IDS:  # Добавьте проверку на админа
    #     return
    
    text = "⚙️ *Панель управления*\n\n"
    
    # Статистика
    expired_prizes = manager.get_expired_prizes()
    text += f"🔄 Доступно для повторной отправки: {len(expired_prizes)}\n"
    
    bot.send_message(user_id, text, parse_mode='Markdown', reply_markup=gen_admin_markup())

@bot.callback_query_handler(func=lambda call: call.data.startswith('retry_get_'))
def callback_retry_get(call):
    """Обработка получения приза при повторной отправке"""
    try:
        prize_id = int(call.data.split('_')[2])
        user_id = call.from_user.id
        
        # Проверяем, может ли пользователь получить этот приз
        if manager.can_get_prize_retry(prize_id, user_id):
            # Получаем приз
            success = manager.add_prize_retry(user_id, prize_id)
            
            if success:
                img = manager.get_prize_img(prize_id)
                with open(f'img/{img}', 'rb') as photo:
                    bot.send_photo(user_id, photo, caption="🎉 Ура! Ты получил приз при повторной отправке!")
                bot.answer_callback_query(call.id, "Поздравляем с получением приза! 🎁")
            else:
                bot.answer_callback_query(call.id, "Ты уже получал этот приз!")
        else:
            bot.answer_callback_query(call.id, "Ты уже получал этот приз ранее!")
    
    except Exception as e:
        print(f"Ошибка: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка")

@bot.callback_query_handler(func=lambda call: call.data.startswith('retry_later_'))
def callback_retry_later(call):
    """Отложить получение приза"""
    prize_id = int(call.data.split('_')[2])
    bot.answer_callback_query(call.id, "Приз будет доступен позже ⏰")

@bot.callback_query_handler(func=lambda call: call.data == 'admin_retry')
def callback_admin_retry(call):
    """Админ: отправить приз повторно"""
    user_id = call.from_user.id
    
    # Находим приз для повторной отправки
    expired_prizes = manager.get_expired_prizes()
    
    if expired_prizes:
        # Берем первый доступный приз
        prize_id, img_name, _ = expired_prizes[0]
        
        # Сбрасываем приз
        manager.reset_prize_for_retry(prize_id)
        
        # Отправляем всем пользователям
        for user in manager.get_users():
            try:
                # Скрываем изображение (если нужно)
                hide_img(img_name)
                
                with open(f'hidden_img/{img_name}', 'rb') as photo:
                    bot.send_photo(user, photo, 
                                  caption="🔄 Повторная отправка приза!",
                                  reply_markup=gen_markup(prize_id))
            except:
                pass
        
        bot.answer_callback_query(call.id, f"Приз #{prize_id} отправлен повторно!")
    else:
        bot.answer_callback_query(call.id, "Нет призов для повторной отправки")
# ===== КОНЕЦ НОВЫХ КОМАНД =====

# ===== СУЩЕСТВУЮЩИЙ КОД =====
def shedule_thread():
    schedule.every().minute.do(send_message) # Здесь ты можешь задать периодичность отправки картинок
    while True:
        schedule.run_pending()
        time.sleep(1)

@bot.message_handler(commands=['start'])
def handle_start(message):
    user_id = message.chat.id
    if user_id in manager.get_users():
        bot.reply_to(message, "Ты уже зарегестрирован!")
    else:
        manager.add_user(user_id, message.from_user.username)
        bot.reply_to(message, """Привет! Добро пожаловать! 
Тебя успешно зарегистрировали!
Каждый час тебе будут приходить новые картинки и у тебя будет шанс их получить!
Для этого нужно быстрее всех нажать на кнопку 'Получить!'

Только три первых пользователя получат картинку!)""")

@bot.message_handler(commands=['rating'])
def handle_rating(message):
    res = manager.get_rating() 
    res = [f'| @{x[0]:<11} | {x[1]:<11}|\n{"_"*26}' for x in res]
    res = '\n'.join(res)
    res = f'|USER_NAME    |COUNT_PRIZE|\n{"_"*26}\n' + res
    bot.send_message(message.chat.id, res)
    
# ===== ДОБАВЛЯЕМ ОБРАБОТЧИК ДЛЯ КНОПКИ "Получить!" =====
@bot.callback_query_handler(func=lambda call: call.data.isdigit())
def callback_get_prize(call):
    """Обработка нажатия кнопки 'Получить!'"""
    prize_id = int(call.data)
    user_id = call.from_user.id
    
    if manager.get_winners_count(prize_id) < 3:
        res = manager.add_winner(user_id, prize_id)
        if res:
            img = manager.get_prize_img(prize_id)
            with open(f'img/{img}', 'rb') as photo:
                bot.send_photo(user_id, photo, caption="Поздравляем! Ты получил картинку!")
        else:
            bot.send_message(user_id, 'Ты уже получил картинку!')
    else:
        bot.send_message(user_id, "К сожалению, ты не успел получить картинку! Попробуй в следующий раз!)")
# ===== КОНЕЦ ОБРАБОТЧИКА =====

def polling_thread():
    bot.polling(none_stop=True)

if __name__ == '__main__':
    manager = DatabaseManager(DATABASE)
    manager.create_tables()

    polling_thread = threading.Thread(target=polling_thread)
    polling_shedule  = threading.Thread(target=shedule_thread)

    polling_thread.start()
    polling_shedule.start()
