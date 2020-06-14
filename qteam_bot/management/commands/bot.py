from django.core.management.base import BaseCommand
from django.conf import settings
from telegram import Bot
from telegram import Update
#from telegram import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from telegram.ext import CallbackContext
from telegram.ext import CommandHandler, CallbackQueryHandler, MessageHandler
from telegram.ext import Filters
from telegram.ext import MessageHandler
from telegram.ext import Updater
from telegram.utils.request import Request
from aiogram.types import Message, CallbackQuery
from collections import defaultdict
import requests
from nltk import regexp_tokenize
import logging
import aiogram
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types.inline_keyboard import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.types.reply_keyboard import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from channels.db import database_sync_to_async
from asgiref.sync import sync_to_async

def norm_name(name):
    name_regex = '[a-zA-Zа-яА-Я]+|\d+'
    return regexp_tokenize((name).lower(), name_regex)


def get_n_grams(name, ngram_len):
    a = norm_name(str(name).lower())
    if len(a) <= ngram_len:
        return [' '.join(a)]

    res_list = []
    for i in range(len(a) - ngram_len + 1):
        res_list.append(' '.join(a[i:i + ngram_len]))
    return res_list


def find_comp_in_msg(msg, company_name):
    comp_toks_num = len(norm_name(company_name))
    company_name = ' '.join(norm_name(company_name))

    tokens_list = get_n_grams(msg, comp_toks_num)
    scores_list = []
    for sub_name in tokens_list:
        scores_list.append(fuzz.ratio(sub_name, company_name))
    return max(scores_list)


def get_best_keyword_match(msg, kw_to_id, th):
    score_dict = {}
    for cmp_name, brand_ind in kw_to_id.items():
        score_dict[cmp_name] = find_comp_in_msg(msg, cmp_name)
    my_dict = pd.Series(score_dict).sort_values().iloc[-1:].to_dict()

    res_list = []
    for name in sorted(score_dict, key=score_dict.get, reverse=True):
        if score_dict[name] < th:
            continue
        res_list += kw_to_id[name]
    return res_list


from telegram import (InputMediaVideo, InputMediaPhoto, InputMediaAnimation, Message, InputFile,
                      InputMediaAudio, InputMediaDocument, PhotoSize)

import telebot
from telebot import types
import json

from qteam_bot.models import BotUser,Store, StoreCategory,StartEvent,CardShowList, MessageLog, OrgSubscription, AcurBot
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
MAX_CAPTION_SIZE = 1000

def log_errors(f):
    def inner(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            error_message = 'Произошла плохая ошибка: {}'.format(e)
            print(error_message)
            raise e

    return inner






class Command(BaseCommand):

    async def get_bot_user(self, from_user):
        try:
            bot_user = await database_sync_to_async(BotUser.objects.get)(bot_user_id=str(from_user.id), bot=self.acur_bot)
        except BotUser.DoesNotExist:
            bot_user = await database_sync_to_async(BotUser.objects.create)(bot_user_id=str(from_user.id),
                                              first_name=from_user.first_name if from_user.first_name else "",
                                              last_name=from_user.last_name if from_user.last_name else "",
                                              username=from_user.username if from_user.username else "",
                                              bot=self.acur_bot,
                                              last_active=timezone.now())
        except BotUser.MultipleObjectsReturned:
            bot_user = await database_sync_to_async(BotUser.objects.filter)(bot_user_id=str(from_user.id), bot=self.acur_bot)[0]

        return bot_user

    def handle_welcome(self, update: Update, context: CallbackContext):

        bot_user = self.get_bot_user(update.message.from_user)
        bot_user.upd_last_active()

        StartEvent.objects.create(bot_user=bot_user)

        update.message.reply_photo(self.bot_config['welcome_photo_url'],
                                   caption=self.bot_config['welcome_text'][:MAX_CAPTION_SIZE], parse_mode="Markdown")



    async def load_mags(self):
        import time

        print('before_pickle')
        df = pd.read_pickle(self.bot_config['load_data_pickle_path'])
        print('after pickle')
        for ind, row in df.iterrows():
            print(ind)
            try:
                store_cat = await database_sync_to_async(StoreCategory.objects.get)(title=row['intent'])
            except StoreCategory.DoesNotExist:
                store_cat = await database_sync_to_async(StoreCategory.objects.create)(title=row['intent'])

            is_avail_for_subscr = not row['intent'] in ['wc', 'bankomat']
            print('after store_cat')
            store = await database_sync_to_async(Store.objects.create)(
                    is_active=row['is_active'],
                    title=row['long_name'],
                    brand=row['short_name'],
                    keywords=row['keywords'],
                    alter_names=row['atler_names'],
                    short_descr=row['short_descr'],
                    long_descr=row['long_descr'],
                    floor=int(row['floor']),
                    phone_number='',
                    plan_image=row['map'],
                    store_image=row['store'],
                    bot=self.acur_bot,
                    is_availible_for_subscription=is_avail_for_subscr,
                    cat=store_cat)

            print('store', store)
            store.get_plan_pic_file_id(self.dp.bot)
            #store.get_store_pic_file_id(context.bot)

            # context.bot.send_media_group(chat_id=update.effective_chat.id, media=[inp_photo, inp_photo2])
            # time.sleep(2)


    async def get_orgs_tree_dialog_teleg_params(self, node_id, orgs_add_to_show = []):
        print('get_orgs_tree_dialog_teleg_params')
        print(self.org_hier_dialog)
        node_info = [node for node in self.org_hier_dialog if node['node_id'] == node_id][0]
        print('node_info', node_info)
        text = node_info['text']


        #keyboard = []
        keyboard = InlineKeyboardMarkup()

        if node_info['type'] == 'dnode':
            for btn in node_info['btns']:
                btn_prev = InlineKeyboardButton(text=btn['text'],
                                                callback_data=json.dumps(
                                                    {'node_id': btn['dest'],
                                                     'dial_id': 'spisok',
                                                     'type': 'dialog'
                                                    }))
                #keyboard.append([btn_prev])
                keyboard.add(btn_prev)

        if node_info['type'] == 'show_orgs':
            print("if node_info['type'] == 'show_orgs':")
            intent_res = await database_sync_to_async( Store.objects.filter)(cat__title__in = node_info['intents_list'], bot = self.acur_bot)
            #print('intent_res', intent_res)
            intent_res = await sync_to_async(list)(intent_res)
            if node_info['l_str_bound_eq']:
                intent_res = [org for org in intent_res if org.title>=node_info['l_str_bound_eq']]
            if node_info['r_str_bound_neq']:
                intent_res = [org for org in intent_res if org.title<node_info['r_str_bound_neq']]

            extra_list = Store.objects.filter(pk__in = node_info['extra_orgs_list'])
            extra_list = list(extra_list)+list(orgs_add_to_show)




            print('intent_res, extra_list', intent_res, extra_list)
            stores_to_show = list(set(intent_res)|set(extra_list))
            print('stores_to_show', stores_to_show)

            text += '\n'
            text += ('\n').join(["{}. {}".format(i+1, org.get_inlist_descr()) for i, org in enumerate(stores_to_show)])
            len(text)
            print('text', text)

            keyboard_line_list = []
            for i, org in enumerate(stores_to_show):
                btn = InlineKeyboardButton(text=str(i+1),
                                                callback_data=json.dumps(
                                                    {'type': 'show_org',
                                                     'org_id': org.id}))
                keyboard_line_list.append(btn)
                if i % 3 == 3 - 1:
                    keyboard.row(*keyboard_line_list)
                    keyboard_line_list = []
            if keyboard_line_list:
                keyboard.row(*keyboard_line_list)

            btn = InlineKeyboardButton(text='Назад',
                                       callback_data=json.dumps(
                                           {'node_id': node_info['back_node_id'],
                                            'dial_id': 'spisok',
                                            'type': 'dialog'}))
            keyboard.row(btn)

        print('keyboard',keyboard)
        return {"text":text ,
                "parse_mode": "Markdown",
                "reply_markup": keyboard}

    def load_model(self, config_path='acur_intent_config.json'):
        import copy

        import pickle
        my_config = json.load(open(config_path))
        tmp_config = copy.deepcopy(my_config)
        tmp_config['chainer']['out'] = ['y_pred_labels', 'y_pred_probas']
        tmp_config['chainer']['pipe'][-2]['out'] = ['y_pred_ids', 'y_pred_probas']
        self.model = build_model(tmp_config)
        #self.in_2_label = pickle.load(open('in_2_label.pkl', 'rb'))
        print('модель загрузили кое-как')

    @log_errors
    def handle_spisok(self, update: Update, context: CallbackContext):

        print('handle spisok')

        bot_user = self.get_bot_user(update.message.from_user)
        bot_user.upd_last_active()

        print('before json.load')

        text = "Это начала диалога  про список магазинов"
        root_node_id = 0
        print('before params')
        params =  self.get_orgs_tree_dialog_teleg_params(root_node_id)
        print('after params')
        print('params', params)
        update.message.reply_text(params['text'],
                                        reply_markup=params['reply_markup'],
                                        parse_mode=params['parse_mode'])

    @log_errors
    def handle_opened(self, update: Update, context: CallbackContext):

        print('handle spisok')

        bot_user = self.get_bot_user(update.message.from_user)
        bot_user.upd_last_active()

        print('before json.load')

        orgs_list = list(Store.objects.filter(is_active=True, bot = self.acur_bot))
        if len(orgs_list) > 50:
            update.message.reply_text(
                'Карантин закончился, открыто более 50 магазинов!\nВоспользуйтесь обычным списком!',
                parse_mode="Markdown")
        else:
            params = self.get_orgs_tree_dialog_teleg_params(-2, orgs_list)
            update.message.reply_text(params['text'],
                                      reply_markup=params['reply_markup'],
                                      parse_mode=params['parse_mode'])

    @log_errors
    async def get_card_message_telegram_req_params(self, org, bot_user):
        text = org.get_card_text()

        keyboard = []
        keyboard = InlineKeyboardMarkup()
        if not org.is_availible_for_subscription:
            return {"text": text,
                    "parse_mode": "Markdown",
                    "reply_markup": InlineKeyboardMarkup(keyboard)}

        print('before subscr get')
        subscription = await database_sync_to_async(OrgSubscription.objects.filter)(bot_user=bot_user, org=org)
        subscription = await sync_to_async(list)(subscription)


        if not subscription:
            subscribe_btn = InlineKeyboardButton(text="Подписаться", callback_data=json.dumps({'org_id': org.id, 'type': 'subscr'}))
        else:
            subscribe_btn = InlineKeyboardButton(text="Отписаться",
                                                 callback_data=json.dumps({'org_id': org.id, 'type': 'unsubscr'}))
        keyboard.row(subscribe_btn)

        return {"text": text,
                "parse_mode": "Markdown",
                "reply_markup": keyboard}



    @log_errors
    async def org_find_name_keywords(self, query):

        kw_to_ind = defaultdict(list)
        print('self.acur_bot', self.acur_bot)
        stores_list = await database_sync_to_async(Store.objects.filter)(bot = self.acur_bot)
        stores_list = await sync_to_async(list)(stores_list)
        for store in stores_list:
            if str(store.keywords) in ['nan', '']:
                continue
            for kw in store.keywords.split(','):
                kw_to_ind[kw.strip().lower()] += [store.id]

        brand_name_to_id = defaultdict(list)
        for store in stores_list:
            mag_short_name = store.brand.strip().lower()
            brand_name_to_id[mag_short_name] += [store.id]

            brand_name_to_id[cyrtranslit.to_cyrillic(mag_short_name, 'ru')] += [store.id]

            if str(store.alter_names) in ['nan', '']:
                continue
            for kw in store.alter_names.split(','):
                brand_name_to_id[kw.strip().lower()] += [store.id]

        print(brand_name_to_id)
        print(kw_to_ind)
        return get_best_keyword_match(query, brand_name_to_id, 80)+get_best_keyword_match(query, kw_to_ind, 75)

    @log_errors
    async def prebot(self, msg):
        print('in prebot')
        name_result_list = await self.org_find_name_keywords(msg)
        #name_result_list = []
        if name_result_list:
            stores = await database_sync_to_async(Store.objects.filter)(pk__in=name_result_list)
            stores = await sync_to_async(list)(stores)
            #return 'Возможно, вы имели в виду:\n' + '\n'.join(map(lambda x: x.title, stores))
            return -1, stores

        r = requests.get(self.bot_config['model_api_url'], data={'context': msg})
        intent_type =r.json()['intent_type']
        print('intent_type', intent_type)
        print('self.intent_to_node[intent_type]', self.intent_to_node[intent_type])
        #intent_type = 'juveliry'


        #stores = Store.objects.filter(cat=StoreCategory.objects.get(title=intent_type))
        return self.intent_to_node[intent_type], []



    def add_arguments(self, parser):
        parser.add_argument('config_path', type=str, help='Path to tc_bot_config')



    def handle(self, *args, **kwargs):
        self.help = 'Телеграм-бот'
        config_path = kwargs['config_path']

        self.bot_config = json.load(open(config_path))
        print('bot_config readed')

        self.org_hier_dialog = self.bot_config['org_hier_dialog']
        self.intent_to_node = self.bot_config['intent_to_node']
        self.TOKEN = self.bot_config['token']


        # Configure logging
        logging.basicConfig(level=logging.DEBUG)

        # Initialize bot and dispatcher
        bot = Bot(token=self.TOKEN)
        dp = Dispatcher(bot)
        self.dp=dp

        async def on_start(dp: aiogram.Dispatcher):
            me = await self.dp.bot.get_me()
            bot_defaults = {'telegram_bot_id': me['id'],
                            'first_name': me['first_name'],
                            'username': me['username']}
            print('bot_defaults', bot_defaults)
            self.acur_bot, _ = await database_sync_to_async( AcurBot.objects.update_or_create)(
                token=self.TOKEN, defaults=bot_defaults
            )



        @self.dp.message_handler(regexp='(^cat[s]?$|puss)')
        async def cats(message: types.Message):
            with open('data/cats.jpg', 'rb') as photo:
                '''
                # Old fashioned way:
                await bot.send_photo(
                    message.chat.id,
                    photo,
                    caption='Cats are here 😺',
                    reply_to_message_id=message.message_id,
                )
                '''

                await message.reply_photo(photo, caption='Cats are here 😺')

        #@dp.message_handler()
        #async def echo(self, message: types.Message):
        #    # old style:
        #    # await bot.send_message(message.chat.id, message.text)

        #    await message.answer(self.help)



        @self.dp.message_handler()
        async def msg_handler(message: types.Message):
            bot_user = await self.get_bot_user(message.from_user)
            print('bot_user', bot_user)
            await database_sync_to_async(bot_user.upd_last_active)()
            await database_sync_to_async(MessageLog.objects.create)(bot_user=bot_user, text=message.text)

            if message.text == 'загрузите данные':
                await self.load_mags()
                await message.answer(text='Загрузили!')
                return

            node_id_to_show, org_list = await self.prebot(message.text)
            print('org_list', org_list)

            params =await self.get_orgs_tree_dialog_teleg_params(node_id_to_show, org_list)
            print('params',params)
            await message.answer(params['text'],
                                      reply_markup=params['reply_markup'],
                                      parse_mode=params['parse_mode'])




        @self.dp.callback_query_handler()
        async def keyboard_callback_handler(callback: CallbackQuery):
            data = callback.data
            real_data = json.loads(data)
            print('real_data', real_data)

            bot_user = await self.get_bot_user(callback.from_user)
            print('bot_user', bot_user)
            await database_sync_to_async(bot_user.upd_last_active)()

            if real_data['type'] == 'dialog' and real_data['dial_id'] == 'spisok':
                node_id = real_data['node_id']
                print('dest_node_id_from_btn_handler')
                params =await self.get_orgs_tree_dialog_teleg_params(node_id)
                print('after get_orgs_tree_dialog_teleg_params')
                await callback.message.edit_text(params['text'],
                                        reply_markup=params['reply_markup'],
                                        parse_mode=params['parse_mode'])

            if real_data['type'] in ['show_org'] and 'org_id' in real_data:
                    try:
                        if 'org_id' in real_data:
                            org = await database_sync_to_async(Store.objects.get)(pk=real_data['org_id'], bot=self.acur_bot)
                    except Store.DoesNotExist:
                        return

                    #token = await database_sync_to_async(org.get_token)()
                    #print('token',token )
                    photo_id = await org.get_plan_pic_file_id(self.dp.bot)

                    params = await self.get_card_message_telegram_req_params(org, bot_user)
                    await callback.message.answer_photo(
                                           photo=photo_id,
                                           caption=params['text'][:MAX_CAPTION_SIZE],
                                           parse_mode=params['parse_mode'],
                                           reply_markup=params['reply_markup'])



            if real_data['type'] == 'subscr' and 'org_id' in real_data:
                try:
                    org = await database_sync_to_async(Store.objects.get)(pk=real_data['org_id'], bot=self.acur_bot)
                except Store.DoesNotExist:
                    return

                await database_sync_to_async(OrgSubscription.objects.create)(bot_user=bot_user, org=org)
                await callback.answer(show_alert=False, text="Вы успешно подписаны!")
                print('after create')
                params = await self.get_card_message_telegram_req_params(org, bot_user)
                print('after get_card_message_telegram_req_params')
                await callback.message.edit_caption(params['text'][:MAX_CAPTION_SIZE],
                                           reply_markup=params['reply_markup'],
                                           parse_mode=params['parse_mode'])

            if real_data['type'] == 'unsubscr' and 'org_id' in real_data:
                try:
                    org = await database_sync_to_async(Store.objects.get)(pk=real_data['org_id'], bot=self.acur_bot)
                except Store.DoesNotExist:
                    return
                print('unsubscr')
                subs_list = await database_sync_to_async(OrgSubscription.objects.filter)(bot_user=bot_user, org=org)
                await database_sync_to_async(subs_list.delete)()

                await callback.answer(show_alert=False, text="Вы успешно отписаны!")
                params = await self.get_card_message_telegram_req_params(org, bot_user)
                await callback.message.edit_caption(params['text'][:MAX_CAPTION_SIZE],
                                           reply_markup=params['reply_markup'],
                                           parse_mode=params['parse_mode'])

        #updater.dispatcher.add_handler(CommandHandler('start', self.handle_welcome))
        #updater.dispatcher.add_handler(CommandHandler('spisok', self.handle_spisok))
        #updater.dispatcher.add_handler(CommandHandler('opened', self.handle_opened))

        #updater.dispatcher.add_handler(MessageHandler(Filters.all,self.msg_handler))
        #updater.dispatcher.add_handler(CallbackQueryHandler(self.keyboard_callback_handler, pass_chat_data=True))

        #updater.dispatcher.add_handler(MessageHandler(Filters.text, self.msg_handler))

        # 3 -- запустить бесконечную обработку входящих сообщений
        #updater.start_polling()
        #updater.idle()


        executor.start_polling(dp, skip_updates=True, on_startup=on_start,)