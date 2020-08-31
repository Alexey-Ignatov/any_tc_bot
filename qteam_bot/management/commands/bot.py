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
from aiogram.types.input_media import InputMediaPhoto
from channels.db import database_sync_to_async
from asgiref.sync import sync_to_async, async_to_sync
from django.apps import apps
from telebot import types
from aiogram.types import ContentTypes
from qteam_bot.models import BotUser,Store, StoreCategory,StartEvent,CardShowList,\
    MessageLog, OrgSubscription, AcurBot,SavedAnswer,PictureList
import asyncio
import numpy as np

from django.utils import timezone


import json
import pandas as pd
from fuzzywuzzy import fuzz
import cyrtranslit
MAX_CAPTION_SIZE = 1000


def extr_nouns(expl_str):
    if not expl_str:
        return expl_str
    r = requests.post('http://localhost:5000/model', data=json.dumps({'x': [expl_str]}),
                      headers={"content-type": "application/json", 'accept': 'application/json'})
    synt_res = r.json()[0][0]
    reg_nouns = [l.split('\t')[2] for l in synt_res.split('\n')[:-1] if l.split('\t')[3] in ['NOUN']]
    return ' '.join(reg_nouns)


def spellcheck(text):
    params = {'text': text}
    r = requests.get("https://speller.yandex.net/services/spellservice.json/checkText", params=params)
    if r.ok and r.json():
        return text.replace(r.json()[0]['word'], r.json()[0]['s'][0])
    return text


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


class TextProcesser:
    def predict(self, name):
        th1 = .75
        th2 = .1
        r = requests.get('http://127.0.0.1:8000/model/?format=json', data={'context': name})
        res_dict = r.json()['intent_list']
        most_rel_intents_ser = pd.Series(res_dict).sort_values(ascending=False)[:3]
        if most_rel_intents_ser.sum() < th1:
            return ['ukn']
        if (most_rel_intents_ser > th2).any():
            return most_rel_intents_ser[most_rel_intents_ser > th2].to_dict()
        return ['ukn']

    def org_find_name_keywords(self, query):
        kw_to_ind = defaultdict(list)

        for store in self.stores_list:
            if str(store.keywords) in ['nan', '']:
                continue
            for kw in store.keywords.split(','):
                kw_to_ind[kw.strip().lower()] += [store.id]

        brand_name_to_id = defaultdict(list)
        for store in self.stores_list:
            mag_short_name = store.brand.strip().lower()
            brand_name_to_id[mag_short_name] += [store.id]

            brand_name_to_id[cyrtranslit.to_cyrillic(mag_short_name, 'ru')] += [store.id]

            if str(store.alter_names) in ['nan', '']:
                continue
            for kw in store.alter_names.split(','):
                brand_name_to_id[kw.strip().lower()] += [store.id]

        return get_best_keyword_match(query, brand_name_to_id, 90), get_best_keyword_match(query, kw_to_ind, 90)

    def fing_prod_props(self, msg):
        prod_type_inds = sum([self.prod_name_to_indlist[w] for w in norm_name(msg) + extr_nouns(msg).split(' ') if
                              w in self.prod_name_to_indlist], [])

        if not prod_type_inds:
            return [], {}

        cur_prod_df = self.prods_df_enriched[self.prods_df_enriched.index.isin(prod_type_inds)]
        print(cur_prod_df)
        be_in_url_to_inds = cur_prod_df.groupby('store_url').groups
        be_in_url_and_prods = []
        be_in_url_and_props = []
        for url in cur_prod_df.store_url.value_counts().index:
            ind_list = be_in_url_to_inds[url]
            prods_data = cur_prod_df.loc[ind_list, :].reset_index()[['name', 'picture', 'price']].T.to_dict().values()
            be_in_url_and_prods += [(url, prods_data)]

            cur_props = {}
            mean_list = [prod['price'] for prod in prods_data if str(prod['price']) != 'nan']
            cur_props['mean_price'] = np.mean(mean_list) if mean_list else None
            cur_props['example_pics'] = sorted(
                [prod['picture'] for prod in prods_data if str(prod['picture']) != 'nan'])[:9]
            be_in_url_and_props.append((url, cur_props))

        store_id_to_props = {}
        res_stores = []
        for be_in_link, props in be_in_url_and_props:
            stores = [store for store in self.stores_list if store.be_in_link == be_in_link]
            if not stores:
                continue
            res_stores.append(stores[0])
            store_id_to_props[stores[0].id] = props

        return res_stores, store_id_to_props

    def process(self, msg, final_try=False):
        print(msg)
        name_result_list, kw_result_list = self.org_find_name_keywords(msg)
        name_result_list_extr, kw_result_list_extr = self.org_find_name_keywords(extr_nouns(msg))

        ind_to_store_dict = {store.id: store for store in self.stores_list}

        name_result_list = list(map(ind_to_store_dict.__getitem__, name_result_list + name_result_list_extr))
        kw_result_list = list(map(ind_to_store_dict.__getitem__, kw_result_list + kw_result_list_extr))

        ind_relevance = defaultdict(int)
        for org_id in set(name_result_list):
            ind_relevance[org_id.id] += 10000

        for org_id in set(kw_result_list):
            ind_relevance[org_id.id] += 1000

        prod_org_list, org_id_to_props = self.fing_prod_props(msg)
        for org in prod_org_list:
            ind_relevance[org.id] += 100

        print('prod_org_list', [org.title for org in prod_org_list])
        print('kw name', [org.title for org in name_result_list + kw_result_list])

        # r = requests.get('http://127.0.0.1:8000/model/?format=json', data={'context': msg})
        intent_list = self.predict(msg)

        print(intent_list)
        intent_org_list = [store for store in self.stores_list if set(json.loads(store.intent_list)) & set(intent_list)]
        for org in intent_org_list:
            ind_relevance[org.id] += sum([v for k, v in intent_list.items() if k in set(json.loads(org.intent_list))],
                                         0)
            if org.is_top:
                ind_relevance[org.id] += 50

        print('intent_org_list', [org.title for org in intent_org_list])
        stores = name_result_list + kw_result_list + prod_org_list + intent_org_list
        stores = list(set(stores))

        stores_inds_order = sorted(stores, key=lambda x: ind_relevance[x.id], reverse=True)[:15]

        for org in stores:
            if not org.id in org_id_to_props:
                org_id_to_props[org.id] = {'mean_price': np.nan, 'example_pics': []}

        if not stores_inds_order and not final_try:
            return self.process(spellcheck(msg), final_try=True)
        return stores_inds_order, org_id_to_props

        if not stores:
            # if final_try:

            return -2, [], ['ukn']
            # else:
            # self.prebot(spellcheck(msg), final_try=True)
        return -1, stores, list(intent_list.values())


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

        #print('before_pickle')
        old_orgs = await database_sync_to_async(Store.objects.filter)(bot=self.acur_bot)
        await database_sync_to_async(old_orgs.delete)()
        df = pd.read_pickle(self.bot_config['load_data_pickle_path'])
        #print('after pickle')
        for ind, row in df.iterrows():
            #print(ind)
            try:
                store_cat = await database_sync_to_async(StoreCategory.objects.get)(title=row['intent'])
            except StoreCategory.DoesNotExist:
                store_cat = await database_sync_to_async(StoreCategory.objects.create)(title=row['intent'])

            is_avail_for_subscr = not row['intent'] in ['wc', 'bankomat']
            #print('after store_cat')
            store = await database_sync_to_async(Store.objects.create)(
                    is_active=row['is_active'],
                    title=row['long_name'],
                    brand=row['short_name'],
                    keywords=row['keywords'],
                    alter_names=row['atler_names'],
                    short_descr=row['short_descr'],
                    long_descr=row['long_descr'],
                    floor=str(row['floor']),
                    phone_number='',#row['phone'] if str(row['phone']) != 'nan' else '',
                    pic_urls=row['photos'] if str(row['photos']) != 'nan' else json.dumps([]),
                    plan_image=row['map_new'],
                    store_image=row['store'],
                    bot=self.acur_bot,
                    is_availible_for_subscription=is_avail_for_subscr,
                    cat=store_cat,
                    be_in_link = row['be_in_link'] if row['be_in_link']!='no_link' else row['input_url'],
                    is_top = row['top']=='top',
                    intent_list=row['intent_new'],
                    assort_kw =row['assort_kw']
            )

            await store.get_plan_pic_file_id(self.dp.bot)
            #store.get_store_pic_file_id(context.bot)

            await asyncio.sleep(.5)

        stores_list = await database_sync_to_async(Store.objects.filter)(bot=self.acur_bot)
        stores_list = await sync_to_async(list)(stores_list)
        text_bot = TextProcesser()
        prods_df = pd.read_pickle('new_prods_df.pickle')

        text_bot.stores_list = stores_list

        row_list = []
        for cur_org in text_bot.stores_list:
            for kw in cur_org.assort_kw.split(','):
                if not kw.strip():
                    continue
                row_template = pd.Series(np.nan, index=prods_df.iloc[0, :].index)
                row_template['name'] = kw.strip()
                row_template['search_kw'] = [kw.strip()]
                row_template['store_url'] = cur_org.be_in_link
                row_list.append(row_template)

        add_prods_df = pd.DataFrame(row_list)
        prods_df_enriched = prods_df.append(add_prods_df).reset_index().iloc[:, 1:]

        prod_name_to_indlist = defaultdict(list)
        for ind, row in prods_df_enriched.iterrows():
            for kw in row['search_kw']:
                prod_name_to_indlist[kw].append(ind)

        text_bot.prod_name_to_indlist = prod_name_to_indlist
        text_bot.prods_df_enriched = prods_df_enriched
        text_bot.in_2_label = pd.read_pickle('in_2_label.pkl')

        self.text_bot = text_bot
            # context.bot.send_media_group(chat_id=update.effective_chat.id, media=[inp_photo, inp_photo2])

    async def fing_prod_props(self,msg):
        prod_type_to_ind = {kw: [i] for i, kw in enumerate(self.wear_kws)}
        ind_to_prod_type = {i: kw for i, kw in enumerate(self.wear_kws)}
        prod_type_inds = get_best_keyword_match(msg, prod_type_to_ind, 90)
        if not prod_type_inds:
            prod_type_inds = get_best_keyword_match(extr_nouns(msg), prod_type_to_ind, 90)

        if not prod_type_inds:
            return [], {}
        prod_type = ind_to_prod_type[prod_type_inds[0]]

        cur_prod_df = self.prods_df[(self.prods_df.name.str.lower().str.contains(prod_type))]
        be_in_url_to_inds = cur_prod_df.groupby('store_url').groups
        be_in_url_and_prods = []
        be_in_url_and_props = []
        for url in cur_prod_df.store_url.value_counts().index:
            ind_list = be_in_url_to_inds[url]
            be_in_url_and_prods += [(url, cur_prod_df.loc[ind_list, :].reset_index() \
                [['name', 'picture', 'price']].T.to_dict().values())]

            cur_props = {}
            cur_props['mean_price'] = np.mean([prod['price'] for prod in be_in_url_and_prods[-1][1]])
            cur_props['example_pics'] = sorted([prod['picture'] for prod in be_in_url_and_prods[-1][1]])[:9]
            be_in_url_and_props.append((url, cur_props))

        store_id_to_props = {}
        res_stores = []
        for be_in_link, props in be_in_url_and_props:
            stores = await database_sync_to_async(Store.objects.filter)(be_in_link=be_in_link,
                                                                        bot=self.acur_bot)
            stores = await sync_to_async(list)(stores)
            if not stores:
                continue
            res_stores.append(stores[0])
            store_id_to_props[stores[0].id] = props

        return res_stores, store_id_to_props


    async def get_orgs_tree_dialog_teleg_params(self,
                                                node_id,
                                                orgs_add_to_show = [],
                                                back_btn = False,
                                                org_id_to_text = {},
                                                org_id_to_pic_list = {} ):
        #print('get_orgs_tree_dialog_teleg_params')
        node_info = [node for node in self.org_hier_dialog if node['node_id'] == node_id][0]
        #print('node_info', node_info)
        text = node_info['text']


        #keyboard = []
        keyboard = InlineKeyboardMarkup()

        if node_info['type'] == 'dnode':
            for btn in node_info['btns']:
                btn_prev = InlineKeyboardButton(text=btn['text'],
                                                callback_data=json.dumps(
                                                    {'node_id': btn['dest'],
                                                     'type': 'dialog'
                                                    }))
                #keyboard.append([btn_prev])
                keyboard.add(btn_prev)

        if node_info['type'] == 'show_orgs':
            #print("if node_info['type'] == 'show_orgs':")
            intent_res = await database_sync_to_async( Store.objects.filter)(cat__title__in = node_info['intents_list'], bot = self.acur_bot)
            
            intent_res = await sync_to_async(list)(intent_res)
            #print('intent_res', intent_res)
            if node_info['l_str_bound_eq']:
                intent_res = [org for org in intent_res if org.title>=node_info['l_str_bound_eq']]
            if node_info['r_str_bound_neq']:
                intent_res = [org for org in intent_res if org.title<node_info['r_str_bound_neq']]

            #extra_list = Store.objects.filter(pk__in = node_info['extra_orgs_list'])
            #extra_list = list(extra_list)+list(orgs_add_to_show)
            #stores_to_show = orgs_add_to_show
            stores_to_show = intent_res + orgs_add_to_show

            lines_list = []
            for i, org in enumerate(stores_to_show):
                cur_title = org.get_inlist_descr()
                if org.id in org_id_to_text:
                    cur_title = org_id_to_text[org.id]
                lines_list+=["{}. {}".format(i+1,cur_title)]
            text += '\n'
            text += ('\n').join(lines_list)

            keyboard_line_list = []
            for i, org in enumerate(stores_to_show):

                callback_dict = {'type': 'show_org',
                                 'org_id': org.id,
                                 'plist': org_id_to_pic_list[org.id] if org.id in org_id_to_pic_list else ''}
                btn = InlineKeyboardButton(text=str(i+1),
                                                callback_data=json.dumps(callback_dict))
                keyboard_line_list.append(btn)
                if i % 3 == 3 - 1:
                    keyboard.row(*keyboard_line_list)
                    keyboard_line_list = []
            if keyboard_line_list:
                keyboard.row(*keyboard_line_list)

            if back_btn:
                btn = InlineKeyboardButton(text='Назад',
                                           callback_data=json.dumps(
                                               {'node_id': node_info['back_node_id'],
                                                'type': 'dialog'}))
                keyboard.row(btn)

        btn_prev = InlineKeyboardButton(text="Связаться с оператором",
                                        callback_data=json.dumps({'type': 'operator'}))

        keyboard.row(btn_prev)

        return {"text":text ,
                "parse_mode": "Markdown",
                "reply_markup": keyboard}


    async def get_card_message_telegram_req_params(self, org, bot_user):
        text = org.get_card_text()

        keyboard = InlineKeyboardMarkup()
        return {"text": text,
                "parse_mode": "Markdown",
                "reply_markup": keyboard}

        """
        if not org.is_availible_for_subscription:
            return {"text": text,
                    "parse_mode": "Markdown",
                    "reply_markup": InlineKeyboardMarkup(keyboard)}

        #print('before subscr get')
        
        subscription = await database_sync_to_async(OrgSubscription.objects.filter)(bot_user=bot_user, org=org)
        subscription = await sync_to_async(list)(subscription)
        if not subscription:
            subscribe_btn = InlineKeyboardButton(text="Подписаться", callback_data=json.dumps({'org_id': org.id, 'type': 'subscr'}))
        else:
            subscribe_btn = InlineKeyboardButton(text="Отписаться",
                                                 callback_data=json.dumps({'org_id': org.id, 'type': 'unsubscr'}))
        keyboard.row(subscribe_btn)
        """




        async def org_find_name_keywords(self, query):
            kw_to_ind = defaultdict(list)
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


        return get_best_keyword_match(query, brand_name_to_id, 90)+get_best_keyword_match(query, kw_to_ind, 90)



    async def prebot(self, msg, final_try=False):

        name_result_list = await self.org_find_name_keywords(msg)
        name_result_list += await self.org_find_name_keywords(extr_nouns(msg))
        #name_result_list = []


        r = requests.get(self.bot_config['model_api_url'], data={'context': msg})
        intent_list =r.json()['intent_list']
        
        #intent_type = pd.Series(predict_dict).sort_values().index[-1]
        #intent_list = [k for k, v in predict_dict.items() if v > .1]
        #intent_list = sorted(intent_list, key=predict_dict.__getitem__, reverse=True )

        #intent_type = 'juveliry'

        if name_result_list:
            stores = await database_sync_to_async(Store.objects.filter)(pk__in=name_result_list)
            stores = await sync_to_async(list)(stores)

        else:
            stores = await database_sync_to_async(Store.objects.filter)(cat__title__in=intent_list,
                                                                        bot=self.acur_bot)
            stores = await sync_to_async(list)(stores)

        #print('stores', stores)
        used_intents = []
        top_num = 0
        ind_relevance = {}
        for i, store in enumerate(stores):
            intent = await database_sync_to_async(store.get_intent_name)()
            ind_relevance[i] = -intent_list.index(intent)  if intent in intent_list else -100
            if store.is_top:
                ind_relevance[i]+=50
                top_num+=1
            #used_intents.append(intent)
        #intent_list = [intent for intent in intent_list if intent in used_intents]

        stores_inds_order = sorted(list(range(len(stores))), key=ind_relevance.__getitem__, reverse=True)
        stores = [stores[ind] for ind in stores_inds_order][:max(15, top_num)]
        if not stores:
            #if final_try:

            return -2, [], ['ukn']
            #else:
                #self.prebot(spellcheck(msg), final_try=True)
        return -1, stores, intent_list



    def add_arguments(self, parser):
        parser.add_argument('config_path', type=str, help='Path to tc_bot_config')



    def handle(self, *args, **kwargs):
        self.help = 'Телеграм-бот'
        self.config_path = kwargs['config_path']

        self.bot_config = json.load(open(self.config_path))
        #print('bot_config readed')

        self.org_hier_dialog = self.bot_config['org_hier_dialog']
        self.intent_to_node = self.bot_config['intent_to_node']
        self.TOKEN = self.bot_config['client_token']
        self.admin_token = self.bot_config['admin_token']
        self.intent_to_name = self.bot_config['intent_to_name']


        # Configure logging
        logging.basicConfig(level=logging.DEBUG)

        # Initialize bot and dispatcher
        bot = Bot(token=self.TOKEN)
        #async_to_sync(bot.send_message)(646380871,text='хули надо?')

        dp = Dispatcher(bot)
        self.dp=dp

        async def on_start(dp: aiogram.Dispatcher):
            import pickle
            me = await self.dp.bot.get_me()
            bot_defaults = {'telegram_bot_id': me['id'],
                            'first_name': me['first_name'],
                            'username': me['username']}
            #apps.get_app_config('qteam_bot').botid_to_botobj[bot_defaults['telegram_bot_id']]=self.dp.bot


            self.acur_bot, _ = await database_sync_to_async( AcurBot.objects.update_or_create)(
                token=self.TOKEN, defaults=bot_defaults
            )
            self.prods_df = pd.read_pickle('prods_df.pickle')
            self.wear_kws = pickle.load( open('wear_kws.pickle', 'rb'))


        @self.dp.message_handler(commands=['operator'])
        async def handle_operator(message: types.Message):
            bot_user = await self.get_bot_user(message.from_user)
            await database_sync_to_async(bot_user.upd_last_active)()

            bot_user.is_operator_dicussing = True
            await database_sync_to_async(bot_user.save)()
            await message.answer('Напишите запрос оператору:')



        @self.dp.message_handler(commands=['start'])
        async def handle_welcome(message: types.Message):

            bot_user = await self.get_bot_user(message.from_user)
            await database_sync_to_async(bot_user.upd_last_active)()

            await database_sync_to_async(StartEvent.objects.create)(bot_user=bot_user)
            org = await database_sync_to_async(Store.objects.filter)(title="В школу на всех парусах!", bot=self.acur_bot)
            org = await sync_to_async(list)(org)
            # keyboard = []
            keyboard = InlineKeyboardMarkup()
            if org:
                org = org[0]
                callback_dict = {'type': 'show_org',
                                 'org_id': org.id,
                                 'plist': ''}
                btn = InlineKeyboardButton(text="В школу на всех парусах!",
                                           callback_data=json.dumps(callback_dict))
                keyboard.row(btn)


            await message.answer_photo(self.bot_config['welcome_photo_url'],
                                       caption=self.bot_config['welcome_text'][:MAX_CAPTION_SIZE],
                                       reply_markup=keyboard,
                                       parse_mode="Markdown")



        @self.dp.message_handler()
        async def msg_handler(message: types.Message):
            bot_user = await self.get_bot_user(message.from_user)
            await database_sync_to_async(bot_user.upd_last_active)()
            await database_sync_to_async(MessageLog.objects.create)(bot_user=bot_user, text=message.text)

            if message.text == 'загрузите данные':
                await self.load_mags()
                await message.answer(text='Загрузили!')
                return


            if bot_user.is_operator_dicussing:
                admin_acur_bot = await database_sync_to_async( AcurBot.objects.get)(token=self.admin_token)

                r = requests.post('http://localhost:8001/messaging/msg_to_operator/', data={'text':message.text,
                                                                            'sender_user_id': bot_user.bot_user_id,
                                                                            'to_teleg_bot_id': admin_acur_bot.telegram_bot_id,
                                                                            'user_to_bot_msg_id': message.message_id,
                                                                            'from_teleg_bot_id':self.acur_bot.telegram_bot_id})
                bot_user.is_operator_dicussing = False
                await database_sync_to_async(bot_user.save)()
                return

            intent_list = []
            node_id_to_show = -1
            org_list, org_id_to_props = self.text_bot.process(message.text)
            org_id_to_text = {}
            org_id_to_pic_list = {}

            for org in org_list:
                if org_id_to_props[org.id]['mean_price']:
                    org_id_to_text[org.id] = org.get_inlist_descr(
                        "(~{} руб.)".format(int(org_id_to_props[org.id]['mean_price'])))
                else:
                    org_id_to_text[org.id] = org.get_inlist_descr()
                pic_list = org_id_to_props[org.id]['example_pics']
                plit = await database_sync_to_async(PictureList.objects.create)(json_data=json.dumps(pic_list))
                org_id_to_pic_list[org.id] = plit.id

            #print(org_id_to_props)
            #if not org_list:
            #    node_id_to_show, org_list, intent_list = await self.prebot(message.text)
            #    org_id_to_text = {}
            #    org_id_to_pic_list = {}
            #if intent_list and intent_list[0] == 'ukn':
            #    node_id_to_show, org_list, intent_list = -3,[],[]
            #back_btn = node_id_to_show != -1
            back_btn = False
            params = await self.get_orgs_tree_dialog_teleg_params(node_id_to_show,
                                                                  org_list,
                                                                  back_btn=back_btn,
                                                                  org_id_to_text=org_id_to_text,
                                                                  org_id_to_pic_list=org_id_to_pic_list)
            
            ans_dict = {'node_id_to_show':node_id_to_show,
                        'org_list':[org.id for org in org_list],
                        'intent_list':intent_list}
            saved_answer  = await database_sync_to_async( SavedAnswer.objects.create)(json_data=json.dumps(ans_dict))

            if node_id_to_show == -1:
                for intent_type in intent_list:
                    if intent_type not in self.intent_to_name:
                        continue
                    btn_prev = InlineKeyboardButton(text="Все из категории "+self.intent_to_name[intent_type],
                                                    callback_data=json.dumps(
                                                        {'node_id': self.intent_to_node[intent_type],
                                                         'type': 'dialog',
                                                         'saved_id':saved_answer.id,
                                                        }))
                    params['reply_markup'].row(btn_prev)


            await message.answer(params['text'],
                                      reply_markup=params['reply_markup'],
                                      parse_mode=params['parse_mode'])


        @self.dp.callback_query_handler()
        async def keyboard_callback_handler(callback: CallbackQuery):
            data = callback.data
            real_data = json.loads(data)
            #print('real_data', real_data)

            bot_user = await self.get_bot_user(callback.from_user)
            await database_sync_to_async(bot_user.upd_last_active)()

            if real_data['type'] == 'operator':
                bot_user.is_operator_dicussing = True
                await database_sync_to_async(bot_user.save)()
                await callback.message.answer('Напишите запрос оператору:')
                return

            if real_data['type'] == 'dialog':
                node_id = real_data['node_id']
                #print('dest_node_id_from_btn_handler')
                params =await self.get_orgs_tree_dialog_teleg_params(node_id)
                #print('after get_orgs_tree_dialog_teleg_params')

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
                    #await callback.message.answer_photo(
                    #                       photo=photo_id,
                    #                       caption=params['text'][:MAX_CAPTION_SIZE],
                    #                       parse_mode=params['parse_mode'],
                    #                       reply_markup=params['reply_markup'])
                    media = [InputMediaPhoto(media=photo_id,
                                             caption=params['text'][:MAX_CAPTION_SIZE],
                                             parse_mode=params['parse_mode'],)]

                    if not real_data['plist']:
                        for photo_id in json.loads(org.pic_urls)[:8]:
                            media.append(InputMediaPhoto(photo_id))
                    else:
                        plist = await database_sync_to_async(PictureList.objects.get)(pk=real_data['plist'])
                        for photo_id in json.loads(plist.json_data)[:8]:
                            media.append(InputMediaPhoto(photo_id))
                    
                    # await bot.send_media_group(message.from_user.id, media)
                    await callback.message.answer_media_group(media)




            @self.dp.message_handler(commands=['spisok'])
            async def handle_spisok(message: types.Message):


                bot_user = await self.get_bot_user(message.from_user)
                await database_sync_to_async(bot_user.upd_last_active)()

                #print('before json.load')

                text = "Это начала диалога  про список магазинов"
                root_node_id = 0
                #print('before params')
                params = await self.get_orgs_tree_dialog_teleg_params(root_node_id)
                #print('after params')
                await message.answer(params['text'],
                                     reply_markup=params['reply_markup'],
                                     parse_mode=params['parse_mode'])




        @self.dp.channel_post_handler(content_types=ContentTypes.ANY)
        async def my_channel_post_handler(message: types.Message):
            my_users = await database_sync_to_async(BotUser.objects.filter)( bot=self.acur_bot)
            my_users = await sync_to_async(list)(my_users)

            for bot_user in my_users:
                await message.forward(bot_user.bot_user_id)

        executor.start_polling(dp, skip_updates=True, on_startup=on_start,)