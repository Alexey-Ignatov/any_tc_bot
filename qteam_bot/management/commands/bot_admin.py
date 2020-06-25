from django.core.management.base import BaseCommand
from telegram import Bot
from aiogram.types import Message, CallbackQuery
from collections import defaultdict
import requests
from nltk import regexp_tokenize
import logging
import aiogram
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types.inline_keyboard import InlineKeyboardButton, InlineKeyboardMarkup
from channels.db import database_sync_to_async
from asgiref.sync import sync_to_async, async_to_sync
from django.apps import apps
from telebot import types
from django.db.models import Q

from qteam_bot.models import BotUser,Store, StoreCategory,StartEvent,CardShowList, MessageLog, OrgSubscription, AcurBot,InterBotMsg


from django.utils import timezone


import json
import pandas as pd
from fuzzywuzzy import fuzz
import cyrtranslit
MAX_CAPTION_SIZE = 1000



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

            await store.get_plan_pic_file_id(self.dp.bot)
            #store.get_store_pic_file_id(context.bot)

            # context.bot.send_media_group(chat_id=update.effective_chat.id, media=[inp_photo, inp_photo2])
            # time.sleep(2)


    async def get_orgs_tree_dialog_teleg_params(self, node_id, orgs_add_to_show = []):
        print('get_orgs_tree_dialog_teleg_params')
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

            stores_to_show = list(set(intent_res)|set(extra_list))

            text += '\n'
            text += ('\n').join(["{}. {}".format(i+1, org.get_inlist_descr()) for i, org in enumerate(stores_to_show)])

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

        return {"text":text ,
                "parse_mode": "Markdown",
                "reply_markup": keyboard}


    def add_arguments(self, parser):
        parser.add_argument('config_path', type=str, help='Path to tc_bot_config')



    def handle(self, *args, **kwargs):
        self.help = 'Телеграм-бот'
        self.config_path = kwargs['config_path']

        self.bot_config = json.load(open(self.config_path))
        print('bot_config readed')

        self.TOKEN = self.bot_config['admin_token']
        self.client_token = self.bot_config['client_token']
        self.auth_code = self.bot_config['auth_code']

        # Configure logging
        logging.basicConfig(level=logging.DEBUG)

        # Initialize bot and dispatcher
        bot = Bot(token=self.TOKEN)
        #async_to_sync(bot.send_message)(646380871,text='хули надо?')

        dp = Dispatcher(bot)
        self.dp=dp

        async def on_start(dp: aiogram.Dispatcher):
            me = await self.dp.bot.get_me()
            bot_defaults = {'telegram_bot_id': me['id'],
                            'first_name': me['first_name'],
                            'username': me['username']}
            #apps.get_app_config('qteam_bot').botid_to_botobj[bot_defaults['telegram_bot_id']]=self.dp.bot
            self.acur_bot, _ = await database_sync_to_async( AcurBot.objects.update_or_create)(
                token=self.TOKEN, defaults=bot_defaults
            )




        @self.dp.message_handler()
        async def msg_handler(message: types.Message):
            bot_user = await self.get_bot_user(message.from_user)
            await database_sync_to_async(bot_user.upd_last_active)()
            await database_sync_to_async(MessageLog.objects.create)(bot_user=bot_user, text=message.text)

            if message.reply_to_message:
                print('message.reply_to_message', message.reply_to_message.message_id)
                client_acur_bot = await database_sync_to_async(AcurBot.objects.get)(token=self.client_token)
                ##todo проверить пришло ли что-то
                inter_bot_msg = await database_sync_to_async(InterBotMsg.objects.get)\
                    (bot_to_receiver_msg_id = str(message.reply_to_message.message_id), receiver_bot_user =bot_user)

                r = requests.post('http://localhost:8001/messaging/', data={'text':'ответ оператора:  ' + message.text,
                                                                            'sender_user_id': bot_user.bot_user_id,
                                                                            'to_teleg_bot_id': client_acur_bot.telegram_bot_id,
                                                                            'user_to_bot_msg_id': message.message_id,
                                                                            'receiver_user_id':await database_sync_to_async(inter_bot_msg.get_sender_bot_user_teleg_id)(),
                                                                            'from_teleg_bot_id':self.acur_bot.telegram_bot_id,
                                                                            'reply_to':inter_bot_msg.sender_to_bot_msg_id})

                finQ =~Q(receiver_bot_user=bot_user)
                finQ &= Q(user_to_operator_msg_list=await database_sync_to_async(
                    inter_bot_msg.get_user_to_operator_msg_list)())

                other_inter_bot_msg = await database_sync_to_async(InterBotMsg.objects.filter)(finQ)
                other_inter_bot_msg = await sync_to_async(list)(other_inter_bot_msg)
                print('other_inter_bot_msg',len(other_inter_bot_msg))
                for msg in other_inter_bot_msg:
                    user_id = await database_sync_to_async(msg.get_receiver_bot_user_teleg_id)()
                    await self.dp.bot.delete_message(int(user_id),int(msg.bot_to_receiver_msg_id))
                    await database_sync_to_async(msg.delete)()
                    print('other_inter_bot_msg')


            if message.text == self.auth_code:
                bot_user.is_operator = True
                await database_sync_to_async(bot_user.save)()
                await message.answer('Код принят!')



                #await apps.get_app_config('qteam_bot').botid_to_botobj[1233905933].send_message(bot_user.bot_user_id,text='хули надо?')


                return



        @self.dp.callback_query_handler()
        async def keyboard_callback_handler(callback: CallbackQuery):
            data = callback.data
            real_data = json.loads(data)
            print('real_data', real_data)

            bot_user = await self.get_bot_user(callback.from_user)
            await database_sync_to_async(bot_user.upd_last_active)()



            @self.dp.message_handler(commands=['start'])
            async def handle_welcome(message: types.Message):

                bot_user = await self.get_bot_user(message.from_user)

                await database_sync_to_async(bot_user.upd_last_active)()

                await database_sync_to_async(StartEvent.objects.create)(bot_user=bot_user)

                await message.answer_photo(self.bot_config['welcome_photo_url'],
                                           caption=self.bot_config['welcome_text'][:MAX_CAPTION_SIZE],
                                           parse_mode="Markdown")


        executor.start_polling(dp, skip_updates=True, on_startup=on_start,)