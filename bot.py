import telebot
import os
from telebot import types
import time

bot = telebot.TeleBot('933432063:AAEEpMlhBXxveo6U-OBwX8p187als-1BesA')

@bot.message_handler(commands=['start'])
def start_message(message):
    bot.send_message(message.chat.id, 'Привет, ты написал мне /start')

name = '';
surname = '';
age = 0;
@bot.message_handler(commands=['reg'])
def start(message):
    bot.send_message(message.from_user.id, "Как тебя зовут?");
    bot.register_next_step_handler(message, get_name); #следующий шаг – функция get_name


def get_name(message): #получаем фамилию
    global name;
    name = message.text;
    bot.send_message(message.from_user.id, 'Какая у тебя фамилия?');
    bot.register_next_step_handler(message, get_surname);

def get_surname(message):
    surname = message.text;
    bot.send_message(message.from_user.id, 'Сколько тебе лет?');
    bot.register_next_step_handler(message, get_age);

def get_age(message):
    while age == 0: #проверяем что возраст изменился
        try:
             age = int(message.text) #проверяем, что возраст введен корректно
        except Exception:
             bot.send_message(message.from_user.id, 'Цифрами, пожалуйста');
        bot.send_message(message.from_user.id, 'Тебе '+str(age)+' лет, тебя зовут '+name+' '+surname+'?')


#@bot.message_handler(content_types=['text'])
#def send_text(message):
#    if message.text == 'Привет':
#        bot.send_message(message.chat.id, 'Привет, мой создатель')
#    elif message.text == 'Пока':
#        bot.send_message(message.chat.id, 'Прощай, создатель')

@bot.message_handler(commands=['test'])
def find_file_ids(message):
    for file in os.listdir('music/'):
        print(file)
        if file.split('.')[-1] == 'ogg':
            bot.send_message(message.chat.id, file)
            f = open('music/'+file, 'rb')
            msg = bot.send_voice(message.chat.id, f, None)
            # А теперь отправим вслед за файлом его file_id
            bot.send_message(message.chat.id, msg.voice.file_id, reply_to_message_id=msg.message_id)
        time.sleep(3)


@bot.message_handler(content_types=["text"])
def default_test(message):
    keyboard = types.InlineKeyboardMarkup()
    url_button = types.InlineKeyboardButton(text="Перейти на Яндекс", url="https://ya.ru")
    keyboard.add(url_button)
    bot.send_message(message.chat.id, "Привет! Нажми на кнопку и перейди в поисковик.", reply_markup=keyboard)



bot.polling()