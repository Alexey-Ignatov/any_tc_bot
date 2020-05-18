from django.core.management.base import BaseCommand
from django.conf import settings
from telegram import Bot
from telegram import Update
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from telegram.ext import CallbackContext
from telegram.ext import CommandHandler, CallbackQueryHandler, MessageHandler
from telegram.ext import Filters
from telegram.ext import MessageHandler
from telegram.ext import Updater
from telegram.utils.request import Request

from telegram import (InputMediaVideo, InputMediaPhoto, InputMediaAnimation, Message, InputFile,
                      InputMediaAudio, InputMediaDocument, PhotoSize)

import telebot
from telebot import types
import json

from qteam_bot.models import BotUser,Store, StoreCategory,StartEvent,CardShowList
from random import shuffle
from telegram.error import Unauthorized
from telegram.error import BadRequest

from django.utils import timezone
import datetime


import json
import pandas as pd
from deeppavlov import train_model, configs, build_model

from fuzzywuzzy import fuzz
import cyrtranslit


def log_errors(f):
    def inner(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            error_message = f'Произошла ошибка: {e}'
            print(error_message)
            raise e

    return inner




def load_mags():
    mags_list = [(0, 'Супермаркет "Азбука вкуса"', 'food'),
                 (1, 'Туристическое агентство "ANEX TOUR"', 'tur_agentstvo'),
                 (2, 'Химчистка "Bianka"', 'himchistka'),
                 (3, 'Салон бытовых услуг "Мультимастер"', 'dom_byta_remont'),
                 (4, 'Товары для рукоделия "Рукодельница"', 'no_cat'),
                 (5, 'Аптека 36,6', 'pharmacy'),
                 (6, 'Магазин ножей и аксессуаров "Messer Meister"', 'posuda'),
                 (7, 'Магазин бытовой химии и косметики "Японочка"', 'kosmetics'),
                 (8, 'Магазин косметики "ORGANIC SHOP"', 'kosmetics'),
                 (9, 'Ортопедические товары\xa0"ОРТОВЕН"', 'pharmacy'),
                 (10, 'Магазин косметики\xa0PROFFLINE', 'kosmetics'),
                 (11, 'Магазин аудио-видео "Dеликатесы stereo"', 'book_media'),
                 (12, 'Цветы', 'flowers'),
                 (13, 'Упаковка подарков\xa0«Все для Праздника»', 'book_media'),
                 (14, 'Кальяны, ремонт телефонов, чехлы', 'dom_byta_remont'),
                 (15, 'Серебро\xa0"925"', 'juveliry'),
                 (16, 'Копи-центр "Реглет"', 'copy_centr'),
                 (17, 'Магазин цифровой мобильной электроники "Ноу-Хау от Билайн"', 'mobile'),
                 (18, 'МТС', 'mobile'),
                 (19, 'Салон оптики "Очкарик"', 'optics'),
                 (20, 'АЛЕФ. Меха, Верхняя одежда, Аксессуары', 'mekh'),
                 (21, 'Магазин обуви "Lauf"', 'galantereya'),
                 (22, 'Дом обуви "ТОФА"', 'galantereya'),
                 (23, 'Магазин косметики и парфюмерии "ИЛЬ ДЕ БОТЭ"', 'kosmetics'),
                 (24, 'Мистер Cумкин', 'galantereya'),
                 (25, 'Ювелирика', 'juveliry'),
                 (26, 'Магазин ювелирных украшений "Адамас"', 'juveliry'),
                 (27, 'Сотовая связь "Теле2"', 'mobile'),
                 (28, 'Магазин ювелирных украшений "Бронницкий ювелир"', 'juveliry'),
                 (29, 'Ремонт телефонов', 'dom_byta_remont'),
                 (30, 'Мегафон', 'mobile'),
                 (31, 'Подарки, украшения, аксессуары', 'juveliry'),
                 (32, 'Табачный "Шерлок"', 'tabac'),
                 (33, 'XIAOMI', 'mobile'),
                 (34, 'Аксессуары для мобильных телефонов', 'mobile'),
                 (35, 'Копи-центр "Реглет"', 'copy_centr'),
                 (36, 'Магазин одежды "GLENFIELD"', 'clothes'),
                 (37, 'Магазин одежды "Love Republic"', 'clothes'),
                 (38, 'Магазин одежды "ZARINA"', 'clothes'),
                 (39, 'Магазин одежды "ТВОЕ"', 'clothes'),
                 (40, 'Магазин одежды "OGGI"', 'clothes'),
                 (41, 'Магазин одежды "befree"', 'clothes'),
                 (42, 'Магазин одежды "Zolla"', 'clothes'),
                 (43, 'Магазин женского белья "LAPASITA"', 'underwear'),
                 (44, 'Магазин одежды\xa0Molly', 'clothes'),
                 (45, 'Шляпы "O`Sofi"', 'clothes'),
                 (46, 'Футболки, поло', 'clothes'),
                 (47, 'Сувениры и подарки', 'juveliry'),
                 (48, 'Студия экспресс-маникюра "Chic"', 'manikur'),
                 (49, 'Наливной парфюм французский', 'kosmetics'),
                 (50, 'Кожгалантерея', 'dom_byta_remont'),
                 (51, 'Косметика КОРА', 'kosmetics'),
                 (52, 'Магазин одежды "JUMP by Zolla"', 'clothes'),
                 (53, 'Магазин спортивного питания\xa0«Atletic Food»', 'sport'),
                 (54, 'Сеть магазинов детских игрушек TOY.RU', 'book_media'),
                 (55, 'Цифровая типография MDM PRINT', 'copy_centr'),
                 (56, 'Тюль на заказ', 'dom_byta_remont'),
                 (57, 'Магазин женской деловой одежды "DRESSCODE"', 'clothes'),
                 (58, 'Сумки "Via Borsa"', 'galantereya'),
                 (59, 'Турагентство "Coral Travel"', 'tur_agentstvo'),
                 (60, 'Магазин женской одежды "Murrey&Co"', 'clothes'),
                 (61, 'Магазин мужской и женской одежды\xa0BnG Wear', 'clothes'),
                 (62, 'Магазин спортивной розничной сети "Спортмастер"', 'sport'),
                 (63, 'Медицинская одежда\xa0"Элит"', 'clothes'),
                 (64, 'Студия красоты "Chic" (педикюр, макияж)', 'manikur'),
                 (65, 'Онлайн Трейд\xa0– интернет-магазин', 'mobile'),
                 (66, 'Хорошее-постельное.ру', 'underwear'),
                 (67, 'PEGAS Touristik турагентство', 'tur_agentstvo')]
    mags_short_list = ['азбука вкуса',
                       'ANEX TOUR',
                       'Bianka',
                       'Мультимастер',
                       'Рукодельница',
                       '36,6',
                       'Messer Meister',
                       'Японочка',
                       'ORGANIC SHOP',
                       'ОРТОВЕН',
                       'PROFFLINE',
                       'Dеликатесы stereo',
                       'Цветы',
                       'Все для Праздника',
                       'Кальяны, ремонт телефонов, чехлы',
                       'Серебро "925"',
                       'Реглет',
                       'Ноу-Хау от Билайн',
                       'МТС',
                       'Очкарик',
                       'АЛЕФ. Меха',
                       'Lauf',
                       'ТОФА',
                       'ИЛЬ ДЕ БОТЭ',
                       'Мистер Cумкин',
                       'Ювелирика',
                       'Адамас',
                       'Теле2',
                       'Бронницкий ювелир',
                       'Ремонт телефонов',
                       'Мегафон',
                       'Подарки, украшения, аксессуары',
                       'Табачный "Шерлок"',
                       'XIAOMI',
                       'Аксессуары для мобильных телефонов',
                       'Реглет',
                       'GLENFIELD',
                       'Love Republic',
                       'ZARINA',
                       'ТВОЕ',
                       'OGGI',
                       'befree',
                       'Zolla',
                       'LAPASITA',
                       'Molly',
                       'O`Sofi',
                       'Футболки, поло',
                       'Сувениры и подарки',
                       'Chic',
                       'Наливной парфюм французский',
                       'Кожгалантерея',
                       'КОРА',
                       'JUMP by Zolla',
                       'Atletic Food',
                       'TOY.RU',
                       'MDM PRINT',
                       'Тюль на заказ',
                       'DRESSCODE',
                       'Via Borsa',
                       'Coral Travel',
                       'Murrey&Co"',
                       'BnG Wear',
                       'Спортмастер',
                       'Элит',
                       'Chic',
                       'Онлайн Трейд – интернет-магазин',
                       'Хорошее-постельное.ру',
                       'PEGAS Touristik']


    for cid, name, cat in mags_list:
        store_cat = StoreCategory.objects.get(title=cat)
        try:
            store = Store.objects.get(id=cid)
            store.is_active = True,
            store.title = name,
            store.brand = mags_short_list[cid],
            store.keywords = '',
            store.cat = store_cat
            store.save()
        except Store.DoesNotExist:
            store = Store.objects.create(id = cid,
                                        is_active= True,
                                        title = name,
                                        brand = mags_short_list[cid],
                                        keywords = '',
                                        cat = store_cat)















def get_bot_user(from_user):
    try:
        bot_user = BotUser.objects.get(bot_user_id=str(from_user.id))
    except BotUser.DoesNotExist:
        bot_user = BotUser.objects.create(bot_user_id=str(from_user.id),
                                          first_name=from_user.first_name if from_user.first_name else "",
                                          last_name=from_user.last_name if from_user.last_name else "",
                                          username=from_user.username if from_user.username else "",
                                          last_active=timezone.now())
    except BotUser.MultipleObjectsReturned:
        bot_user = BotUser.objects.filter(bot_user_id=str(from_user.id))[0]

    return bot_user














def get_card_message_telegram_req_params(org,card_show_list_id, bot_user):
    text ="*{}* \n{}".format(org.title, 'Описание для ' + org.title)

    keyboard = []

    print('in get_card_message_telegram_req_params')

    try:
        print('try start')
        org_id_list = json.loads(CardShowList.objects.get(pk = card_show_list_id).card_list_json)
        print('try end')
    except CardShowList.DoesNotExist:
        print('except')
        org_id_list = []

    nav_btns_line = []
    if org.id in org_id_list:
        org_index = org_id_list.index(org.id)
        if org_index != 0:
            btn_prev = InlineKeyboardButton(text="⬅️ Предыдущее",
                                   callback_data=json.dumps({'org_id': org_id_list[org_index-1], 'type': 'show', 'list_id':card_show_list_id}))
            nav_btns_line.append(btn_prev)
        if org_index != len(org_id_list)-1:
            btn_next = InlineKeyboardButton(text="➡️️ Следующее",
                                   callback_data=json.dumps({'org_id': org_id_list[org_index+1], 'type': 'show', 'list_id':card_show_list_id}))
            nav_btns_line.append(btn_next)

    keyboard.append(nav_btns_line)

    return {"text":text,
            "parse_mode": "Markdown",
            "reply_markup": InlineKeyboardMarkup(keyboard)}











#def msg_handler(update: Update, context: CallbackContext):
#    bot_user = get_bot_user(update.message.from_user)
#    bot_user.upd_last_active()

    #cards_like_list = CardLike.objects.filter(bot_user=bot_user).order_by('?')
#    cards_list = [like.card for like in cards_like_list]

#    store_show_list = CardShowList.objects.create(card_list_json=json.dumps([card.id for card in cards_list]))
#    print('card_show_list', store_show_list)
#    if cards_list:
#        title_card =cards_list[0]
#        print('title_card', title_card)
#        params = get_card_message_telegram_req_params(title_card,store_show_list.id, bot_user)
#        print('params', params)

#        msg = update.message.reply_photo(title_card.pic_file_id, caption=params['text'], parse_mode=params['parse_mode'],
#                                 reply_markup=params['reply_markup'])




@log_errors
def handle_welcome(update: Update, context: CallbackContext):
    bot_user_id = update.message.from_user.id

    bot_user = get_bot_user(update.message.from_user)
    bot_user.upd_last_active()

    StartEvent.objects.create(bot_user=bot_user)

    welcome_text = "*Привет, я QteamBot 👋*\n" \
                   "😷Карантин - время насторожиться, но точно не время раскисать!\n" \
                   "🎯🗓 Распланируйте выходные так, чтобы и вам не было скучно и врачи одобрили.\n\n" \
                   "🔥Введите /weekend проверить свои планы и подобрать что-то новое.\n" \
                   "😎Каждый день я буду подбирать лично для вас 5 новых активностей. \n" \
                   "👌Сразу вносите в план те, что понравились, завтра их уже не будет.\n\n" \
                   "👍Обязательно лайкайте и дизлайкайте активности! На основе этого я строю рекомендации.\n" \
                   "🤙И, конечно, не забывайте делиться идеями с друзьями!\n\n" \
                   "🏎Ну, понеслась!"
    update.message.reply_photo("https://www.sunhome.ru/i/wallpapers/32/hyu-lori-doktor-haus.1024x600.jpg",
                               caption=welcome_text, parse_mode="Markdown")



class Command(BaseCommand):
    def keyboard_callback_handler(self, update: Update, context: CallbackContext):
        query = update.callback_query
        data = query.data
        real_data = json.loads(data)
        print('real_data', real_data)

        bot_user = get_bot_user(update.effective_user)
        bot_user.upd_last_active()

        #try:
        #    if 'org_id' in real_data:
        #        org = Store.objects.get(pk=real_data['org_id'])
        #except Store.DoesNotExist:
        #    return

        if real_data['type'] == 'dialog' and real_data['dial_id'] == 'spisok':
            node_id = real_data['node_id']
            print('dest_node_id_from_btn_handler')
            params = self.get_orgs_tree_dialog_teleg_params(node_id)
            print('after get_orgs_tree_dialog_teleg_params')
            query.edit_message_text(params['text'],
                                      reply_markup=params['reply_markup'],
                                      parse_mode=params['parse_mode']  )

        if real_data['type'] == 'show_org' and 'org_id' in real_data:
            try:
                if 'org_id' in real_data:
                    org = Store.objects.get(pk=real_data['org_id'])
            except Store.DoesNotExist:
               return

            print('before card_text')
            card_text = org.get_card_text()
            print('card_text', card_text)
            # todo капчн ограничен по размеру, а еще нужно экранировать слешом \ спец символы
            inp_photo = InputMediaPhoto(org.get_plan_pic_file_id(context.bot), caption=card_text, parse_mode="Markdown")
            inp_photo2 = InputMediaPhoto(org.get_store_pic_file_id(context.bot))
            context.bot.send_media_group(chat_id=update.effective_chat.id, media=[inp_photo, inp_photo2])
            # OpenCardEvent.objects.create(bot_user=bot_user, card=card)

            #params = get_card_message_telegram_req_params(org, real_data['list_id'], bot_user)
            #print('params obtained')
            ## context.bot.edit_message_media(media="https://www.sunhome.ru/i/wallpapers/32/hyu-lori-doktor-haus.1024x600.jpg",
            ##                               chat_id=update.callback_query.message.chat_id,
            ##                               message_id=update.callback_query.message.message_id)
            #query.edit_message_caption(params['text'],
            #                           reply_markup=params['reply_markup'],
            #                           parse_mode=params['parse_mode'])

    def get_orgs_tree_dialog_teleg_params(self, node_id):

        node_info = [node for node in self.org_hier_dialog if node['node_id'] == node_id][0]

        text = node_info['text']
        keyboard = []
        if node_info['type'] == 'dnode':
            for btn in node_info['btns']:
                btn_prev = InlineKeyboardButton(text=btn['text'],
                                                callback_data=json.dumps(
                                                    {'node_id': btn['dest'],
                                                     'dial_id': 'spisok',
                                                     'type': 'dialog'
                                                    }))
                keyboard.append([btn_prev])

        if node_info['type'] == 'show_orgs':
            intent_res = Store.objects.filter(cat__title__in = node_info['intents_list'])
            extra_list = Store.objects.filter(pk__in = node_info['extra_orgs_list'])
            print('intent_res, extra_list', intent_res, extra_list)
            stores_to_show = list(set(intent_res|extra_list))
            print('stores_to_show', stores_to_show)

            text += '\n'
            text += ('\n').join(["{}. {}".format(i+1, org.get_inlist_descr()) for i, org in enumerate(stores_to_show)])
            print('text', text)

            keyboard_line_list = []
            for i, org in enumerate(stores_to_show):
                btn = InlineKeyboardButton(text=str(i+1),
                                                callback_data=json.dumps(
                                                    {'type': 'show_org',
                                                     'org_id': org.id}))
                keyboard_line_list.append(btn)
                if i % 3 == 3 - 1:
                    keyboard.append(keyboard_line_list)
                    keyboard_line_list = []
            if keyboard_line_list:
                keyboard.append(keyboard_line_list)

            btn = InlineKeyboardButton(text='Назад',
                                       callback_data=json.dumps(
                                           {'node_id': node_info['back_node_id'],
                                            'dial_id': 'spisok',
                                            'type': 'dialog'}))
            keyboard.append([btn])


        return {"text":text ,
                "parse_mode": "Markdown",
                "reply_markup": InlineKeyboardMarkup(keyboard)}

    def load_model(self, config_path='acur_intent_config.json'):
        import copy

        import pickle
        my_config = json.load(open(config_path))
        tmp_config = copy.deepcopy(my_config)
        tmp_config['chainer']['out'] = ['y_pred_labels', 'y_pred_probas']
        tmp_config['chainer']['pipe'][-2]['out'] = ['y_pred_ids', 'y_pred_probas']
        self.model = build_model(tmp_config)
        self.in_2_label = pickle.load(open('in_2_label.pkl', 'rb'))
        print('модель загрузили кое-как')

    def handle_spisok(self, update: Update, context: CallbackContext):

        print('handle spisok')

        bot_user = get_bot_user(update.message.from_user)
        bot_user.upd_last_active()

        print('before json.load')
        self.org_hier_dialog = json.load(open('org_hier_dialog.json', 'r'))

        text = "Это начала диалога  про список магазинов"
        root_node_id = 0
        print('before params')
        params = self.get_orgs_tree_dialog_teleg_params(root_node_id)
        print('after params')
        print('params', params)
        update.message.reply_text(params['text'],
                                        reply_markup=params['reply_markup'],
                                        parse_mode=params['parse_mode'])



    def msg_handler(self, update: Update, context: CallbackContext):
        bot_user = get_bot_user(update.message.from_user)
        bot_user.upd_last_active()

        if update.message.text == 'загрузите данные':
            load_mags()
            context.bot.send_message(chat_id=update.effective_chat.id, text='Загрузили!')
            return

        if update.message.text == 'памагите!':
            context.bot.send_message(chat_id=update.effective_chat.id, text=self.help)
            return

        #annotation, org_list = self.prebot(update.message.text)
        annotation = 'тест анотации'
        org_list = Store.objects.filter(pk__in=[1, 2, 3, 4, 5])
        context.bot.send_message(chat_id=update.effective_chat.id, text=annotation)

        store_show_list = CardShowList.objects.create(card_list_json=json.dumps([org.id for org in org_list]))


        if org_list:
            title_org = org_list[0]
            print('title_card', title_org)
            params = get_card_message_telegram_req_params(title_org, store_show_list.id, bot_user)
            print('params', params)

            print('bot_user.bot_user_id', bot_user.bot_user_id)
            print('update.message.chat_id', update.message.chat_id)
            print('settings.dev_tg_id', settings.dev_tg_id)
            org = Store.objects.get(pk=45)
            print('settings.BASE_DIR + org.plan_image.url',settings.BASE_DIR + org.plan_image.url)
            print(settings.BASE_DIR + org.plan_image.url == '/Users/alexey/any_tc_bot/media/2.png')
            with open('/Users/alexey/any_tc_bot/media/2.png', 'rb') as f:
                context.bot.send_photo(chat_id=settings.dev_tg_id, photo=f)
            # msg = update.message.reply_photo(inp_photo, caption=params['text'],
            #                                  parse_mode=params['parse_mode'],
            #                                  reply_markup=params['reply_markup'])
            #msg = context.bot.send_photo(update.effective_chat.id, inp_photo)
            #update.message.reply_photo(inp_photo)
            #
            #msg = update.message.reply_photo(inp_photo, caption=params['text'],
            #                                 parse_mode=params['parse_mode'],
            #                                 reply_markup=params['reply_markup'])




    def predict(self, name, top=100000):
        res_l, probs = self.model([name])
        print('res_l, probs',res_l, probs)
        res_dict = {}
        for k, v in self.in_2_label.items():
            res_dict[k] = probs[0][v]

        return pd.Series(res_dict).sort_values()[-top:]

    def org_name_find(self, query):
        res_dict = {}
        for store in Store.objects.all():
            mag_short_name = store.brand

            mag_short_name_trnaslit = cyrtranslit.to_cyrillic(mag_short_name.lower(), 'ru')
            score = max(fuzz.partial_ratio(mag_short_name, query), fuzz.partial_ratio(mag_short_name_trnaslit, query))
            res_dict[store.id] = score

        filtered_res = {k: v for k, v in res_dict.items() if v >= 80}
        return sorted(filtered_res, key=filtered_res.get, reverse=True)

    def prebot(self, msg):
        intent_type = self.predict(msg.lower()).index[-1]
        print('intent_type:', intent_type)
        if intent_type=='wc':
            return 'Туалет на втором этаже', []
        if intent_type=='cinema':
            return 'Кинотеатр на третьем этаже', []

        name_result_list = self.org_name_find(msg)

        if name_result_list:
            stores = Store.objects.filter(pk__in=name_result_list)
            #return 'Возможно, вы имели в виду:\n' + '\n'.join(map(lambda x: x.title, stores))
            return 'Возможно, вы имели в виду:', stores

        stores = Store.objects.filter(cat=StoreCategory.objects.get(title=intent_type))
        return 'Посмотрите тут:', stores

    def handle(self, *args, **options):
        self.help = 'Телеграм-бот'
        # 1 -- правильное подключение
        #self.load_model('acur_intent_config.json')
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


        updater = Updater(
            bot=bot,
            use_context=True,
        )

        updater.dispatcher.add_handler(CommandHandler('start', handle_welcome))
        updater.dispatcher.add_handler(CommandHandler('spisok', self.handle_spisok))
        updater.dispatcher.add_handler(MessageHandler(Filters.all,self.msg_handler))
        updater.dispatcher.add_handler(CallbackQueryHandler(self.keyboard_callback_handler, pass_chat_data=True))

        updater.dispatcher.add_handler(MessageHandler(Filters.text, self.msg_handler))

        # 3 -- запустить бесконечную обработку входящих сообщений
        updater.start_polling()
        updater.idle()
