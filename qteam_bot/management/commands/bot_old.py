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
from qteam_bot.models import BotUser,BookEveningEvent, CardLike, CardDislike, Card, DateUserCardSet,CardDate, CardShowList
from qteam_bot.models import OpenCardEvent, GetCardsEvent,GetPlansEvent,StartEvent
from qteam_bot.views import  get_cards_ok_to_show_on_date,date_to_date_dict
import json
from random import shuffle
from telegram.error import Unauthorized
from telegram.error import BadRequest

from django.utils import timezone
import datetime


def get_next_week_and_names():
    res_list = []
    curr_time = timezone.now() + datetime.timedelta(hours=3)
    for i in range(7):
        i_date = (curr_time + datetime.timedelta(days=i)).date()
        res_list.append(date_to_date_dict(i_date))
    return res_list


def log_errors(f):

    def inner(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            error_message = f'Произошла ошибка: {e}'
            print(error_message)
            raise e

    return inner


def get_bot_user(from_user):
    try:
        bot_user = BotUser.objects.get(bot_user_id=str(from_user.id))
    except BotUser.DoesNotExist:
        bot_user = BotUser.objects.create(bot_user_id=str(from_user.id),
                                          first_name=from_user.first_name if from_user.first_name else "" ,
                                          last_name=from_user.last_name if from_user.last_name else "",
                                          username=from_user.username if from_user.username else "",
                                          last_active=timezone.now())
    except BotUser.MultipleObjectsReturned:
        bot_user = BotUser.objects.filter(bot_user_id=str(from_user.id))[0]

    return bot_user


def get_card_message_telegram_req_params(card,card_list_id, bot_user):
    text ="*{}* \n{}".format(card.title, card.card_text)

    keyboard = []

    print('in get_card_message_telegram_req_params')

    try:
        print('try start')
        card_id_list = json.loads(CardShowList.objects.get(pk = card_list_id).card_list_json)
        print('try end')
    except CardShowList.DoesNotExist:
        print('except')
        card_id_list = []

    nav_btns_line = []
    if card.id in card_id_list:
        card_index = card_id_list.index(card.id)

        likes_btns = []

        likes = list(CardLike.objects.filter(bot_user=bot_user, card=card))
        dislikes = list(CardDislike.objects.filter(bot_user=bot_user, card=card))

        if likes:
            likes_btns.append(InlineKeyboardButton(text="👍",
                                                   callback_data=json.dumps({'card_id': card.id, 'type': 'dislike', 'list_id':card_list_id})))
        if dislikes:
            likes_btns.append(InlineKeyboardButton(text="👎",
                                 callback_data=json.dumps({'card_id': card.id, 'type': 'like', 'list_id':card_list_id})))

        if not likes+dislikes:
            likes_btns.append(InlineKeyboardButton(text="👍",
                                                   callback_data=json.dumps({'card_id': card.id, 'type': 'like',
                                                                             'list_id': card_list_id})))
            likes_btns.append(InlineKeyboardButton(text="👎",
                                                   callback_data=json.dumps(
                                                       {'card_id': card.id, 'type': 'dislike', 'list_id': card_list_id})))

        keyboard.append(likes_btns)



        if card_index != 0:
            btn_prev = InlineKeyboardButton(text="⬅️ Назад",
                                   callback_data=json.dumps({'card_id': card_id_list[card_index-1], 'type': 'show', 'list_id':card_list_id}))
            nav_btns_line.append(btn_prev)
        if card_index != len(card_id_list)-1:
            btn_next = InlineKeyboardButton(text="➡️️ Вперед",
                                   callback_data=json.dumps({'card_id': card_id_list[card_index+1], 'type': 'show', 'list_id':card_list_id}))
            nav_btns_line.append(btn_next)

    keyboard.append(nav_btns_line)

    return {"text":text,
            "parse_mode": "Markdown",
            "reply_markup": InlineKeyboardMarkup(keyboard)}



def keyboard_callback_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    data = query.data
    real_data = json.loads(data)
    print('real_data', real_data)

    bot_user = get_bot_user(update.effective_user)
    bot_user.upd_last_active()

    try:
        if 'card_id' in real_data:
            card = Card.objects.get(pk=real_data['card_id'])
    except Card.DoesNotExist:
        return


    if real_data['type'] == 'show':
        OpenCardEvent.objects.create(bot_user=bot_user, card=card)

        params = get_card_message_telegram_req_params(card, real_data['list_id'], bot_user)

        context.bot.edit_message_media(media=InputMediaPhoto(card.pic_file_id),
                                       chat_id=update.callback_query.message.chat_id,
                                       message_id=update.callback_query.message.message_id)
        query.edit_message_caption(params['text'],
                                       reply_markup=params['reply_markup'],
                                       parse_mode=params['parse_mode'] )


    if real_data['type'] == 'like':
        try:
            CardLike.objects.get(bot_user=bot_user, card=card)
        except CardLike.DoesNotExist:
            CardLike.objects.create(bot_user=bot_user, date=timezone.now() + datetime.timedelta(hours=3), card=card)

        dislikes = CardDislike.objects.filter(bot_user=bot_user, card=card)
        for dislike in dislikes:
            dislike.delete()

        query.answer(show_alert=False, text="Предпочтения учтены!")

        OpenCardEvent.objects.create(bot_user=bot_user, card=card)

        params = get_card_message_telegram_req_params(card, real_data['list_id'], bot_user)

        context.bot.edit_message_media(media=InputMediaPhoto(card.pic_file_id),
                                       chat_id=update.callback_query.message.chat_id,
                                       message_id=update.callback_query.message.message_id)
        query.edit_message_caption(params['text'],
                                       reply_markup=params['reply_markup'],
                                       parse_mode=params['parse_mode'] )

    if real_data['type'] == 'dislike':
        try:
            CardDislike.objects.get(bot_user=bot_user, card=card)
        except CardDislike.DoesNotExist:
            CardDislike.objects.create(bot_user=bot_user, date=timezone.now() + datetime.timedelta(hours=3), card=card)

        likes = CardLike.objects.filter(bot_user=bot_user, card=card)
        for like in likes:
            like.delete()

        query.answer(show_alert=False, text="Предпочтения учтены!")

        OpenCardEvent.objects.create(bot_user=bot_user, card=card)

        params = get_card_message_telegram_req_params(card, real_data['list_id'], bot_user)

        context.bot.edit_message_media(media=InputMediaPhoto(card.pic_file_id),
                                       chat_id=update.callback_query.message.chat_id,
                                       message_id=update.callback_query.message.message_id)
        query.edit_message_caption(params['text'],
                                       reply_markup=params['reply_markup'],
                                       parse_mode=params['parse_mode'] )




    #if real_data['type'] == 'delete_card':


def get_possible_cards_on_week(individual_stop_list=[]):
    weekends = get_next_week_and_names()
    print(weekends)
    res_dict = []
    for date_dict in weekends:
        res_dict+=get_cards_ok_to_show_on_date(date=date_dict['date'])

    return list(set(res_dict) - set(individual_stop_list))

def create_card_list_for_user(bot_user):

    liked_cards = [like.card for like in CardLike.objects.filter(bot_user=bot_user)]
    disliked_cards = [like.card for like in CardDislike.objects.filter(bot_user=bot_user)]
    res_cards = get_possible_cards_on_week(individual_stop_list=liked_cards + disliked_cards)

    shuffle(res_cards)
    #shuffle(another_cards_list)

    return res_cards[:5]



def get_user_cards_today(bot_user):
    try:
        date_user_card_set = DateUserCardSet.objects.get(bot_user=bot_user, date=(
                    datetime.datetime.now() + datetime.timedelta(hours=3)).date())
        card_id_list = json.loads(date_user_card_set.card_ids)
        res_cards = Card.objects.filter(pk__in=card_id_list).order_by('id')
        print('get_plan_card_params:from try')
    except DateUserCardSet.DoesNotExist:
        res_cards = create_card_list_for_user(bot_user)
        res_cards.sort(key=lambda x: x.id, reverse=False)

        res_cards_ids = [card.id for card in res_cards]
        DateUserCardSet.objects.create(bot_user=bot_user, date=(datetime.datetime.now() + datetime.timedelta(hours=3)).date(), card_ids=json.dumps(res_cards_ids))

        print('get_plan_card_params:first time')

    return res_cards

@log_errors
def handle_get(update: Update, context: CallbackContext):
    bot_user = get_bot_user(update.message.from_user)
    bot_user.upd_last_active()
    cards_list = get_user_cards_today(bot_user)

    card_show_list = CardShowList.objects.create(card_list_json=json.dumps([card.id for card in cards_list]))

    print('card_show_list', card_show_list)
    if cards_list:
        title_card =cards_list[0]
        params = get_card_message_telegram_req_params(title_card,card_show_list.id, bot_user)
        msg = update.message.reply_photo(title_card.pic_file_id, caption=params['text'], parse_mode=params['parse_mode'],
                                 reply_markup=params['reply_markup'])


def handle_likes(update: Update, context: CallbackContext):
    bot_user = get_bot_user(update.message.from_user)
    bot_user.upd_last_active()

    cards_like_list = CardLike.objects.filter(bot_user=bot_user).order_by('?')
    cards_list = [like.card for like in cards_like_list]

    card_show_list = CardShowList.objects.create(card_list_json=json.dumps([card.id for card in cards_list]))
    print('card_show_list', card_show_list)
    if cards_list:
        title_card =cards_list[0]
        print('title_card', title_card)
        params = get_card_message_telegram_req_params(title_card,card_show_list.id, bot_user)
        print('params', params)

        msg = update.message.reply_photo(title_card.pic_file_id, caption=params['text'], parse_mode=params['parse_mode'],
                                 reply_markup=params['reply_markup'])

@log_errors
def handle_welcome(update: Update, context: CallbackContext):
    bot_user_id = update.message.from_user.id

    bot_user = get_bot_user(update.message.from_user)
    bot_user.upd_last_active()

    StartEvent.objects.create(bot_user=bot_user)

    welcome_text = "*Привет, я QteamBot 👋*\n" \
                   "😷Карантин - время насторожиться, но точно не время раскисать!\n\n" \
                   "😎Каждый день я буду подбирать лично для вас и присылать 5 интересных и полезных активностей, которые не противоречат крантину.\n" \
                   "👍Обязательно лайкайте активности, чтобы пересмотреть их снова. А еще на основе этого я строю рекомендации.\n" \
                   "🤙Введите /likes чтобы посмотреть что вы лайкали.\n" \
                   "P.S. По команде /get можно посмотреть активности на сегодня, если вы их упустили\n\n" \
                   "🏎Ну, понеслась!"
    update.message.reply_photo("https://www.sunhome.ru/i/wallpapers/32/hyu-lori-doktor-haus.1024x600.jpg", caption=welcome_text, parse_mode="Markdown")


def send_dayly_broadcast(update: Update, context: CallbackContext):
    bot_user_id = update.message.from_user.id
    if str(bot_user_id) != '733585869':
        return

    bot_user_list= [bot_user for bot_user in BotUser.objects.all()]

    bot_user_list = [get_bot_user(update.message.from_user)]

    for bot_user in bot_user_list:
        cards_list = get_user_cards_today(bot_user)

        card_show_list = CardShowList.objects.create(card_list_json=json.dumps([card.id for card in cards_list]))

        print('card_show_list', card_show_list)
        if cards_list:
            title_card = cards_list[0]
            params = get_card_message_telegram_req_params(title_card, card_show_list.id, bot_user)
            msg = context.bot.send_photo(bot_user.bot_user_id,title_card.pic_file_id, caption=params['text'],
                                              parse_mode=params['parse_mode'],
                                              reply_markup=params['reply_markup'])


def send_newsletter_broadcast(update: Update, context: CallbackContext):
    bot_user_id = update.message.from_user.id
    if str(bot_user_id) != '733585869':
        return

    bot_user_list=  [bot_user for bot_user in BotUser.objects.all()]
    bot_user_list = [get_bot_user(update.message.from_user)]

    for bot_user in bot_user_list:
        try:
            welcome_text = "*👋Привет!*\n" \
                           "🛠Мы доработали нашего бота, отталкиваясь то ваших пожелний, теперь в нем нет ничего лишнего!\n" \
                           "Фокус мы сохранили на карантин-френдли активностях\n" \
                           "🧨 Нажмите /start , чтобы посмотреть что изменилось!"

            context.bot.send_photo(bot_user.bot_user_id, 'https://miro.medium.com/max/1100/0*iOQP_kfBnBJDB9GQ.png',
                                   caption=welcome_text, parse_mode="Markdown")
        except (Unauthorized, BadRequest):
            pass


def see_all(update: Update, context: CallbackContext):
    bot_user_id = update.message.from_user.id
    if str(bot_user_id) != '733585869':
        return

    cards_to_renew = Card.objects.filter(is_active=True)
    for card in cards_to_renew:
        params =get_card_message_telegram_req_params(card)
        with open(settings.BASE_DIR + card.image.url, 'rb') as f:
            msg = context.bot.send_photo(733585869, f, caption=params['text'], parse_mode=params['parse_mode'], reply_markup=params['reply_markup'])


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


        #cards_to_renew = Card.objects.filter(is_active=True)
        #for card in cards_to_renew:
        #    if not card.image:
        #        continue
        #    print('before_send', settings.BASE_DIR+card.image.url)
        #    with open(settings.BASE_DIR+card.image.url, 'rb') as f:
        #        msg = bot.send_photo(733585869,f)
        #        card.pic_file_id = msg.photo[0].file_id
        #        card.save()


        updater = Updater(
            bot=bot,
            use_context=True,
        )

        updater.dispatcher.add_handler(CommandHandler('start', handle_welcome))
        updater.dispatcher.add_handler(CommandHandler('get', handle_get))
        updater.dispatcher.add_handler(CommandHandler('likes', handle_likes))
        updater.dispatcher.add_handler(CommandHandler('send_dayly_broadcast', send_dayly_broadcast))
        updater.dispatcher.add_handler(CommandHandler('send_newsletter_broadcast', send_newsletter_broadcast))
        updater.dispatcher.add_handler(CommandHandler('see_all', see_all))
        updater.dispatcher.add_handler(CallbackQueryHandler(keyboard_callback_handler, pass_chat_data=True))


        # 3 -- запустить бесконечную обработку входящих сообщений
        updater.start_polling()
        updater.idle()
