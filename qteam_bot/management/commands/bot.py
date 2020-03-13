from django.core.management.base import BaseCommand
from django.conf import settings
from telegram import Bot
from telegram import Update
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackContext
from telegram.ext import CommandHandler, CallbackQueryHandler
from telegram.ext import Filters
from telegram.ext import MessageHandler
from telegram.ext import Updater
from telegram.utils.request import Request
from qteam_bot.models import BotUser,BookEveningEvent, CardLike, CardDislike, Card, DateUserCardSet
from qteam_bot.views import get_next_weekend_and_names, get_cards_ok_to_show_on_date
import json
from random import shuffle

from django.utils import timezone
import datetime

def log_errors(f):

    def inner(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            error_message = f'Произошла ошибка: {e}'
            print(error_message)
            raise e

    return inner


def get_possible_cards_on_weekend(individual_stop_list=[]):
    weekends = get_next_weekend_and_names()
    print(weekends)
    res_dict = []
    for date_dict in weekends:
        res_dict+=get_cards_ok_to_show_on_date(date=date_dict['date'])

    return list(set(res_dict) - set(individual_stop_list))


def get_card_message_telegram_req_params(card,likes_btns=True):
    text ="*{}* \n{}".format(card.title, card.card_text)
    weekends = get_next_weekend_and_names()

    keyboard = []
    if likes_btns:
        likes_btns =[InlineKeyboardButton(text="👍", callback_data=json.dumps({'card_id': card.id, 'type': 'like'})),
                     InlineKeyboardButton(text="👎", callback_data=json.dumps({'card_id': card.id, 'type': 'dislike'}))]

        keyboard.append(likes_btns)

    for date_dict in weekends:
        if card not in get_cards_ok_to_show_on_date(date=date_dict['date']):
            continue
        book_btns =[InlineKeyboardButton(text="✅ В план на {}".format(date_dict['date_text']),
                                         callback_data=json.dumps({'card_id': card.id, 'date': str(date_dict['date']), 'type':'book'}))]

        keyboard.append(book_btns)

    btn = InlineKeyboardButton(text="⬅️ Назад",
                               callback_data=json.dumps({'type': 'back_to_plan'}))
    keyboard.append([btn])

    return {"text":text,
            "parse_mode": "Markdown",
            "reply_markup": InlineKeyboardMarkup(keyboard)}



def keyboard_callback_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    data = query.data

    bot_user_id = update.effective_user.id
    real_data = json.loads(data)
    print('real_data', real_data)

    try:
        bot_user = BotUser.objects.get(bot_user_id=str(bot_user_id))
    except BotUser.DoesNotExist:
        bot_user = BotUser.objects.create(bot_user_id=str(bot_user_id))
    except BotUser.MultipleObjectsReturned:
        bot_user = BotUser.objects.filter(bot_user_id=str(bot_user_id))[0]

    try:
        if 'card_id' in real_data:
            card = Card.objects.get(pk=real_data['card_id'])
    except Card.DoesNotExist:
        return


    if real_data['type'] == 'show':
        params =get_card_message_telegram_req_params(card)
        query.edit_message_text(text=params['text'], parse_mode=params['parse_mode'], reply_markup=params['reply_markup'])

    if real_data['type'] == 'like':
        CardLike.objects.create(bot_user=bot_user, date=timezone.now() + datetime.timedelta(hours=3), card=card)
        query.answer(show_alert=False, text="Предпочтения учтены!")

    if real_data['type'] == 'dislike':
        CardDislike.objects.create(bot_user=bot_user, date=timezone.now() + datetime.timedelta(hours=3), card=card)
        query.answer(show_alert=False, text="Предпочтения учтены!")

    if real_data['type'] == 'book':
        date = datetime.datetime.strptime(real_data['date'], "%Y-%m-%d").date()
        try:
            BookEveningEvent.objects.get(bot_user=bot_user, card=card, planed_date=date)
        except BookEveningEvent.DoesNotExist:
            BookEveningEvent.objects.create(bot_user=bot_user, card=card, planed_date=date)
        query.answer(show_alert=False, text="Активность добавлена в план!")
        params = get_plan_card_params(bot_user)
        query.edit_message_text(text=params['text'], parse_mode=params['parse_mode'],
                                reply_markup=params['reply_markup'])

    if real_data['type'] == 'back_to_plan':
        print('from back_to_plan')
        params = get_plan_card_params(bot_user)
        query.edit_message_text(text=params['text'], parse_mode=params['parse_mode'],
                                reply_markup=params['reply_markup'])


def get_cards_by_user(bot_user):

    liked_cards = [like.card for like in CardLike.objects.filter(bot_user=bot_user)]
    disliked_cards = [like.card for like in CardDislike.objects.filter(bot_user=bot_user)]
    print('bot_user', bot_user)
    res_cards = get_possible_cards_on_weekend(individual_stop_list=liked_cards + disliked_cards)

    shuffle(res_cards)
    res_cards = res_cards[:5]
    return res_cards

def get_plan_card_params(bot_user):
    print('get_plan_card_params')
    try:
        date_user_card_set = DateUserCardSet.objects.get(bot_user=bot_user, date=(
                    datetime.datetime.now() + datetime.timedelta(hours=3)).date())
        card_id_list = json.loads(date_user_card_set.card_ids)
        res_cards = Card.objects.filter(pk__in=card_id_list).order_by('id')
        print('get_plan_card_params:from try')
    except DateUserCardSet.DoesNotExist:
        res_cards = get_cards_by_user(bot_user)
        res_cards.sort(key=lambda x: x.id, reverse=False)

        res_cards_ids = [card.id for card in res_cards]
        DateUserCardSet.objects.create(bot_user=bot_user, date=(datetime.datetime.now() + datetime.timedelta(hours=3)).date(), card_ids=json.dumps(res_cards_ids))

        print('get_plan_card_params:first time')

    dates_list = get_next_weekend_and_names()
    emodzi_list = ["🍕", "️💥", "🔥", "🧠", "👻",
                   "👌", "🥋", "🎣", "⛳", "️🎱", "🏋",
                   "️‍️🛹", "🥌", "🥁", "🎼", "🎯", "🎳",
                   "🎮", "🎲", "🏁", "💡", "🎪", "🏏",
                   "🌪", "🍿", "🏄", "‍️🎉", "🧨", "🎈"]
    shuffle(emodzi_list)

    plans_by_date = []
    keyboard = []
    final_text = ''.join(emodzi_list[:3]) + "*Ваши планы на ближайшие выходные:*\n\n"
    for date_dict in dates_list:
        day_plans_text_list = []
        day_book_events = BookEveningEvent.objects.filter(planed_date=date_dict['date'], bot_user=bot_user)
        for event in day_book_events:
            day_plans_text_list.append(event.card.title)

        curr_plan = {
            'date': date_dict['date'],
            'date_text': date_dict['date_text'],
            'plans_text': ",\n".join(day_plans_text_list)
        }
        plans_by_date.append(curr_plan)

        final_text += '*{}*'.format("🗓" + curr_plan['date_text'] + ": ") + (
            curr_plan['plans_text'] if curr_plan['plans_text'] \
                else "Ничего не запланировано") + '\n\n'


    for card in res_cards:
        btn = InlineKeyboardButton(text=card.title,
                               callback_data=json.dumps({'card_id': card.id, 'type': 'show'}))
        keyboard.append([btn])



    final_text += "\nВыберете развлечение для более подробного просмотра:"

    return {
            'text':final_text,
            'parse_mode' : "Markdown",
            'reply_markup' : InlineKeyboardMarkup(keyboard)
    }


def get_plans(update: Update, context: CallbackContext):
    bot_user_id = update.message.from_user.id
    print('bot_user_id', bot_user_id)
    try:
        bot_user = BotUser.objects.get(bot_user_id=str(bot_user_id))
    except BotUser.DoesNotExist:
        bot_user = BotUser.objects.create(bot_user_id=str(bot_user_id))
    except BotUser.MultipleObjectsReturned:
        bot_user = BotUser.objects.filter(bot_user_id=str(bot_user_id))[0]

    update.message.reply_text(**get_plan_card_params(bot_user))








@log_errors
def do_echo(update: Update, context: CallbackContext):
    chat_id = update.message.from_user.id
    text = update.message.text

    # p, _ = Profile.objects.get_or_create(
    #     external_id=chat_id,
    #     defaults={
    #         'name': update.message.from_user.username,
    #     }
    # )
    # m = Message(
    #     profile=p,
    #     text=text,
    # )
    # m.save()

    reply_text = f'*Ваш ID* = {chat_id}\n{text}'
    update.message.reply_text(
        text=reply_text,
        parse_mode="Markdown"
    )


@log_errors
def handle_welcome(update: Update, context: CallbackContext):
    welcome_text = "*Привет, я QteamBot 👋*\n" \
                   "🎯🗓 Чтобы провести выходные весело и полезно, их нужно обязательно спланировать заранее.\n" \
                   "💡Я напомню что нужно спланировать выходные и предложу варианты по вашим вкусам.\n\n" \
                   "🔥Введите /plan проверить свои планы  на подобрать что-то новое.\n" \
                   "😎Каждый день для вас будут подбираться новые активности.\n\n" \
                   "👍Обязательно лайкайте и дизлайкайте активности! На основе этого я строю рекомендации.\ngetweekendschedule" \
                   "👌После того как вы выбрали активность, вносите их в план, чтобы я был спокоен за ваши выходные и не напоминал вам их планировать!"
    f = open('qteam_bot/pics/man-2087782_1920.jpg', 'rb')

    update.message.reply_photo(f, caption=welcome_text, parse_mode="Markdown")


@log_errors
def do_count(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id

    # p, _ = Profile.objects.get_or_create(
    #     external_id=chat_id,
    #     defaults={
    #         'name': update.message.from_user.username,
    #     }
    # )
    # count = Message.objects.filter(profile=p).count()

    count = 0
    update.message.reply_text(
        text=f'У вас {count} сообщений',
    )

@log_errors
def start(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id

    count = 0
    update.message.reply_text(
        text=f'У вас {count} сообщений',
    )

class Command(BaseCommand):
    help = 'Телеграм-бот'

    def handle(self, *args, **options):
        # 1 -- правильное подключение
        request = Request(
            connect_timeout=0.5,
            read_timeout=1.0,
        )
        bot = Bot(
            request=request,
            token=settings.TOKEN,
            base_url=getattr(settings, 'PROXY_URL', None),
        )
        print(bot.get_me())

        # 2 -- обработчики
        updater = Updater(
            bot=bot,
            use_context=True,
        )

        message_handler = MessageHandler(Filters.text, do_echo)
        updater.dispatcher.add_handler(message_handler)
        updater.dispatcher.add_handler(CommandHandler('count', do_count))
        updater.dispatcher.add_handler(CommandHandler('start', handle_welcome))
        updater.dispatcher.add_handler(CommandHandler('plan', get_plans))
        updater.dispatcher.add_handler(CallbackQueryHandler(keyboard_callback_handler, pass_chat_data=True))


        # 3 -- запустить бесконечную обработку входящих сообщений
        updater.start_polling()
        updater.idle()
