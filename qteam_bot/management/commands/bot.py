from django.core.management.base import BaseCommand
from django.conf import settings
from telegram import Bot
from telegram import Update
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
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
                               callback_data=json.dumps({'type': 'show_new_activities'}))
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
        #update.message.edit_message_text(f, caption=welcome_text, parse_mode="Markdown")
        #query.edit_message_text(text=params['text'], parse_mode=params['parse_mode'], reply_markup=params['reply_markup'])
        #context.bot.send_message(chat_id=update.effective_chat.id, text=static"I'm a bot, please talk to me!")
        context.bot.edit_message_media(media=InputMediaPhoto(card.pic_file_id),
                                       chat_id=update.callback_query.message.chat_id,
                                       message_id=update.callback_query.message.message_id)
        query.edit_message_caption(params['text'],
                                       reply_markup=params['reply_markup'],
                                       parse_mode=params['parse_mode'] )
        #context.bot.edit_message_caption(caption='haha',
        #                         chat_id=update.callback_query.message.chat_id,
        #                         message_id=update.callback_query.message.message_id)
        #context.bot.edit_message_caption(chat_id=update.callback_query.message.chat_id,
        #                                 message_id=update.callback_query.message.message_id,


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
        params = get_plan_card__main_params(bot_user)

        context.bot.edit_message_media(media=InputMediaPhoto(settings.PLAN_PHOTO_TELEGRAM_FILE_ID),
                                       chat_id=update.callback_query.message.chat_id,
                                       message_id=update.callback_query.message.message_id)
        query.edit_message_caption(params['text'],
                                       reply_markup=params['reply_markup'],
                                       parse_mode=params['parse_mode'] )

    if real_data['type'] == 'back_to_main':
        params = get_plan_card__main_params(bot_user)

        context.bot.edit_message_media(media=InputMediaPhoto(settings.PLAN_PHOTO_TELEGRAM_FILE_ID),
                                       chat_id=update.callback_query.message.chat_id,
                                       message_id=update.callback_query.message.message_id)
        query.edit_message_caption(params['text'],
                                       reply_markup=params['reply_markup'],
                                       parse_mode=params['parse_mode'] )

    if real_data['type'] == 'show_new_activities':
        params = get_plan_card_activity_list_params(bot_user)

        context.bot.edit_message_media(media=InputMediaPhoto(settings.PLAN_PHOTO_TELEGRAM_FILE_ID),
                                       chat_id=update.callback_query.message.chat_id,
                                       message_id=update.callback_query.message.message_id)

        print("params", params)
        query.edit_message_caption(params['text'],
                                    reply_markup=params['reply_markup'],
                                   parse_mode = params['parse_mode'] )


    if real_data['type'] == 'show_planed_activities':
        context.bot.edit_message_media(media=InputMediaPhoto(settings.PLAN_PHOTO_TELEGRAM_FILE_ID),
                                       chat_id=update.callback_query.message.chat_id,
                                       message_id=update.callback_query.message.message_id)

        res_cards = get_user_weekend_planed_cards(bot_user)
        keyboard  = get_cards_btns(res_cards)

        final_text = get_user_plans_str(bot_user)
        final_text += "\nВыбирите активность из списка для просмотра"

        back_btn = InlineKeyboardButton(text="⬅️ Назад",
                                        callback_data=json.dumps({'type': 'back_to_main'}))

        keyboard.append([back_btn])

        # final_text += "\nВыберете развлечение для более подробного просмотра:"


        query.edit_message_caption(final_text,
                                       reply_markup=InlineKeyboardMarkup(keyboard),
                                       parse_mode="Markdown")




def get_user_weekend_planed_cards(bot_user):
    dates_list = get_next_weekend_and_names()
    day_plans_text_list = []
    for date_dict in dates_list:
        day_book_events = BookEveningEvent.objects.filter(planed_date=date_dict['date'], bot_user=bot_user)
        for event in day_book_events:
            day_plans_text_list.append(event.card)

    return list(set(day_plans_text_list))



def get_cards_by_user(bot_user):

    liked_cards = [like.card for like in CardLike.objects.filter(bot_user=bot_user)]
    disliked_cards = [like.card for like in CardDislike.objects.filter(bot_user=bot_user)]
    print('bot_user', bot_user)
    res_cards = get_possible_cards_on_weekend(individual_stop_list=liked_cards + disliked_cards)

    shuffle(res_cards)
    res_cards = res_cards[:5]
    return res_cards


def get_cards_btns(cards):
    keyboard =[]
    for card in cards:
        btn = InlineKeyboardButton(text=card.title,
                               callback_data=json.dumps({'card_id': card.id, 'type': 'show'}))
        keyboard.append([btn])
    return keyboard


def get_user_plans_str(bot_user):
    dates_list = get_next_weekend_and_names()
    emodzi_list = ["🍕", "️💥", "🔥", "🧠", "👻",
                   "👌", "🥋", "🎣", "⛳", "️🎱", "🏋",
                   "️‍️🛹", "🥌", "🥁", "🎼", "🎯", "🎳",
                   "🎮", "🎲", "🏁", "💡", "🎪", "🏏",
                   "🌪", "🍿", "🏄", "‍️🎉", "🧨", "🎈"]
    shuffle(emodzi_list)

    plans_by_date = []
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

    return final_text


def get_user_cards_today(bot_user):
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

    return res_cards

def get_plan_card__main_params(bot_user):
    print('get_plan_card_params')
    final_text = get_user_plans_str(bot_user)

    keyboard = []
    #res_cards = get_user_cards_today(bot_user)
    #keyboard += get_cards_btns(res_cards)
    btn_show_new_acts = InlineKeyboardButton(text="️🥁Посмотреть варианты досуга",
                               callback_data=json.dumps({'type': 'show_new_activities'}))
    btn_show_planed_acts = InlineKeyboardButton(text="🧳Открыть запланированные",
                               callback_data=json.dumps({'type': 'show_planed_activities'}))

    keyboard +=[[btn_show_new_acts],[btn_show_planed_acts]]

    #final_text += "\nВыберете развлечение для более подробного просмотра:"

    return {
            'text':final_text,
            'parse_mode' : "Markdown",
            'reply_markup' : InlineKeyboardMarkup(keyboard)
    }


def get_plan_card_activity_list_params(bot_user):
    final_text = get_user_plans_str(bot_user)
    final_text += "\nВыбирите активность из списка для просмотра"

    back_btn = InlineKeyboardButton(text="⬅️ Назад",
                                    callback_data=json.dumps({'type': 'back_to_main'}))

    keyboard = []
    res_cards = get_user_cards_today(bot_user)
    print("get_plan_card_activity_list_params:res_cards", res_cards)
    keyboard += get_cards_btns(res_cards)
    print('get_plan_card_activity_list_params:', keyboard)
    keyboard.append([back_btn])

    # final_text += "\nВыберете развлечение для более подробного просмотра:"

    return {
        'text': final_text,
        'parse_mode': "Markdown",
        'reply_markup': InlineKeyboardMarkup(keyboard)
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

    plan_req_data = get_plan_card__main_params(bot_user)

    with open('qteam_bot/pics/indus_plan.jpg', 'rb') as f :
        msg = update.message.reply_photo(f, caption=plan_req_data['text'],
                                   parse_mode=plan_req_data['parse_mode'],
                                   reply_markup=plan_req_data['reply_markup'])

    settings.PLAN_PHOTO_TELEGRAM_FILE_ID = msg.photo[0].file_id






@log_errors
def handle_welcome(update: Update, context: CallbackContext):
    welcome_text = "*Привет, я QteamBot 👋*\n" \
                   "🎯🗓 Чтобы провести выходные весело и полезно, их нужно обязательно спланировать заранее.\n" \
                   "💡Я напомню что нужно спланировать выходные и предложу варианты по вашим вкусам.\n\n" \
                   "🔥Введите /weekend проверить свои планы  на подобрать что-то новое.\n" \
                   "😎Каждый день для вас будут подбираться новые активности.\n\n" \
                   "👍Обязательно лайкайте и дизлайкайте активности! На основе этого я строю рекомендации.\n" \
                   "👌После того как вы выбрали активность, вносите их в план, чтобы я был спокоен за ваши выходные и не напоминал вам их планировать!"
    f = open('qteam_bot/pics/man-2087782_1920.jpg', 'rb')

    update.message.reply_photo(f, caption=welcome_text, parse_mode="Markdown")



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

        #with open('qteam_bot/pics/indus_plan.jpg', 'rb') as f:
        #    msg = bot.send_photo(733585869,f)
        #    msg.photo[0].file_id

        #print('msg.photo.file_id',msg.photo[0].file_id)


        # 2 -- обработчики
        updater = Updater(
            bot=bot,
            use_context=True,
        )
        cards_to_renew = get_possible_cards_on_weekend()

        #for card in cards_to_renew:
        #    if not card.image:
        #        continue
        #    print('before_send', settings.BASE_DIR+card.image.url)
        #    with open(settings.BASE_DIR+card.image.url, 'rb') as f:
        #        msg = bot.send_photo(733585869,f)
        #        card.pic_file_id = msg.photo[0].file_id
        #        card.save()

        updater.dispatcher.add_handler(CommandHandler('start', handle_welcome))
        updater.dispatcher.add_handler(CommandHandler('weekend', get_plans))
        updater.dispatcher.add_handler(CallbackQueryHandler(keyboard_callback_handler, pass_chat_data=True))


        # 3 -- запустить бесконечную обработку входящих сообщений
        updater.start_polling()
        updater.idle()
