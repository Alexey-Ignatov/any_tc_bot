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
    MessageLog, OrgSubscription, AcurBot,SavedAnswer,PictureList,BtnPressedEvent
import asyncio
import numpy as np

from django.utils import timezone


import json
import pandas as pd
from fuzzywuzzy import fuzz
import cyrtranslit
MAX_CAPTION_SIZE = 1000

import uuid


async def get_answer_by_lotery(req_type, bot_user):
    user_context = json.loads(bot_user.context)
    req_type_to_text = {}
    req_type_to_keyboard = {}
    req_type_to_text['name_kw'] = """Этот чат-бот — новый информационный сервис ТРЦ Океания, и мы хотим показать, чем он может быть вам полезен.

📍 *Задание 1 из 3:*
Поищите любой магазин в ТРЦ Океания, для этого просто напишите мне его название (на оригинальном языке или на русском, например, *Рандеву* или *Rendez-Vous*). Чат-бот поможет найти магазин внутри ТРЦ.
"""

    req_type_to_text['prod'] = """🎉 Ура, первое задание выполнено! 🎉
Чат-бот поможет найти магазин по конкретному товару (лучше всего получается с одеждой).

Вы получите список подходящих магазинов и сможете быстро выбрать, куда пойти, просто нажав на цифру с номером магазина из списка.

Часто чат-бот сообщает о средних ценах на товар, который вы ищете, и показывает примеры моделей, которые продаются в магазине (после выбора магазина нажатием кнопки с цифрой).

📍 *Задание 2 из 3:*
Поищите любой товар из категории одежды (например, *черная футболка*). 
"""
    req_type_to_text['intent'] = """🎉 Осталось всего одно задание! 🎉

Вы также можете быстро и легко найти подходящие торговые точки по категории товаров. 

📍 *Задание 3 из 3:*
Получите список магазинов, поискав любую категорию товаров. Например: *еда, одежда, обувь, украшения*.
"""

    req_type_to_keyboard['name_kw'] = InlineKeyboardMarkup()
    req_type_to_keyboard['prod'] = InlineKeyboardMarkup()
    req_type_to_keyboard['intent'] = InlineKeyboardMarkup()


    if req_type in ['lotery_Falke', 'lotery_Reebok']:
        if [elem for elem in user_context if elem['type'] == 'lotery']:
            return 'Вы уже зарегистрирвоаны на лотерею!', InlineKeyboardMarkup()
        user_context += [{'type': 'lotery',
                          'lotery_branch': '',
                          'search_types_list':  [],
                          'req_statisfied': False,
                          'double_chance': False}]
        if req_type == 'lotery_Falke':
            user_context[-1]['lotery_branch'] = 'Falke'
        else:
            user_context[-1]['lotery_branch'] = 'Reebok'
        bot_user.context = json.dumps(user_context)
        await database_sync_to_async(bot_user.save)()

        repl_text = """⚡️Отлично, вы в игре! ⚡️

Результаты конкурса будут объявлены до 28.12.2020, вам придет сообщение в этом чат-боте, не отключайтесь от него. 

Хотите пройти мини-игру за 60 секунд и *удвоить* свой шанс на выигрыш?"""

        keyboard = InlineKeyboardMarkup()
        btn = InlineKeyboardButton(text="🤑 Хочу! 🤑",
                                   callback_data=json.dumps({'type': 'lotery_full'}))
        keyboard.row(btn)
        return repl_text, keyboard

    if req_type == 'lotery_full':
        if not [elem for elem in user_context if elem['type'] == 'lotery']:
            reply_text = 'Произошло что-то не то, попробуйте снова выбрать типа лотереи!'
            return reply_text ,InlineKeyboardMarkup()

        lotery_dict = [elem for elem in user_context if elem['type'] == 'lotery'][0]
        if lotery_dict['double_chance']:
            reply_text = 'Вы уже удвоили свои шансы однажды!'
            return reply_text ,InlineKeyboardMarkup()
        lotery_dict['double_chance'] = True

        bot_user.context = json.dumps(user_context)
        await database_sync_to_async(bot_user.save)()
        return req_type_to_text['name_kw'], req_type_to_keyboard['name_kw']


    if not [elem for elem in user_context if elem['type'] == 'lotery']:
        return None, None


    lotery_dict = [elem for elem in user_context if elem['type'] == 'lotery'][0]
    if lotery_dict['req_statisfied'] or not lotery_dict['double_chance']:
        return None, None


    if 'name_kw' not in lotery_dict['search_types_list']:
        if req_type == 'name_kw':
            lotery_dict['search_types_list'] = list(set(lotery_dict['search_types_list'] + [req_type]))
            bot_user.context = json.dumps(user_context)
            await database_sync_to_async(bot_user.save)()
            return req_type_to_text['prod'], req_type_to_keyboard['prod']
        else:
            return None, None
    if 'prod' not in lotery_dict['search_types_list'] :
        if req_type == 'prod':
            lotery_dict['search_types_list'] = list(set(lotery_dict['search_types_list'] + [req_type]))
            bot_user.context = json.dumps(user_context)
            await database_sync_to_async(bot_user.save)()
            return req_type_to_text['intent'], req_type_to_keyboard['intent']
        else:
            return None, None
    if 'intent' not in lotery_dict['search_types_list']:
        if req_type == 'intent':
            lotery_dict['search_types_list'] = list(set(lotery_dict['search_types_list'] + [req_type]))
            bot_user.context = json.dumps(user_context)
            await database_sync_to_async(bot_user.save)()
        else:
            return None, None

    if not lotery_dict['req_statisfied'] and 'intent' in lotery_dict['search_types_list']:
        lotery_dict['req_statisfied'] = True
        bot_user.context = json.dumps(user_context)
        await database_sync_to_async(bot_user.save)()

        keyboard = InlineKeyboardMarkup()
        btn = InlineKeyboardButton(text="🔥 Удвоить шансы на победу! 🔥",
                                   callback_data=json.dumps({'type': 'finish_lotery'}))
        keyboard.row(btn)
        repl_text = """🤩 Поздравляем! 🤩

Вы освоили нашего нового чат-бота! Кроме того, чат-бот может ответить на общие вопросы (о парковке, как проехать, часах работы и т.д. и т.п.).

*Ваша заслуженная награда:*
"""
        return repl_text, keyboard
    return 'Пока не получилось выполнить задание, попробуйте ввсети словосочетание из примера!', InlineKeyboardMarkup()




def extr_nouns(expl_str, model_url):
    if not expl_str:
        return expl_str
    r = requests.post(model_url, data=json.dumps({'x': [expl_str]}),
                      headers={"content-type": "application/json", 'accept': 'application/json'})
    synt_res = r.json()[0][0]
    reg_nouns = [l.split('\t')[2] for l in synt_res.split('\n')[:-1] if l.split('\t')[3] not in ['ADV', 'VERB', 'ADP']]
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
        th1 = .7
        th2 = .2
        r = requests.get(self.acur_api_url, data={'context': name})
        res_dict = r.json()['intent_list']
        most_rel_intents_ser = pd.Series(res_dict).sort_values(ascending=False)[:3]
        if most_rel_intents_ser.sum() < th1:
            return {'ukn': 0.}
        if (most_rel_intents_ser > th2).any():
            return most_rel_intents_ser[most_rel_intents_ser > th2].to_dict()
        return {'ukn': 0.}

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

    def find_good_df(self, text):
        res = self.prods_df_enriched.search_kw.to_dict()
        s_tokens = extr_nouns(text, self.morpho_api_url).split(' ')

        if not set(self.wear_kws) &set(s_tokens):
            return pd.DataFrame([], columns = self.prods_df_enriched.columns)

        scores = defaultdict(list)
        for ind, tokens in res.items():
            scores[len(set(tokens) & set(s_tokens))] += [ind]
        if max(scores.keys()) != len(s_tokens):
            return pd.DataFrame([], columns = self.prods_df_enriched.columns)
        inds_set = set(scores[max(scores.keys())])
        return self.prods_df_enriched[self.prods_df_enriched.index.isin(inds_set)]

    def fing_prod_props(self, msg):
        # prod_type_inds = sum([self.prod_name_to_indlist[w] for w in norm_name(msg) + extr_nouns(msg).split(' ') if
        #                      w in self.prod_name_to_indlist], [])

        # if not prod_type_inds:
        #    return [], {}

        cur_prod_df = self.find_good_df(msg)
        if not cur_prod_df.shape[0]:
            return [], {}
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
            if mean_list:
                print(np.mean(mean_list))
            cur_props['example_pics'] = sorted(
                [prod['picture'] for prod in prods_data if str(prod['picture']) != 'nan'])[:9]
            be_in_url_and_props.append((url, cur_props))
        print(be_in_url_and_props)
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
        name_result_list, kw_result_list = self.org_find_name_keywords(msg)
        name_result_list_extr, kw_result_list_extr = self.org_find_name_keywords(extr_nouns(msg, self.morpho_api_url))

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
            if org_id_to_props[org.id]['mean_price']:
                ind_relevance[org.id] += 0.0001

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

        name_kw_stores = name_result_list + kw_result_list
        stores = name_kw_stores if name_kw_stores else prod_org_list + intent_org_list
        stores = list(set(stores))
        stores = sorted(stores, key=lambda x: x.title)

        stores_inds_order = sorted(stores, key=lambda x: ind_relevance[x.id], reverse=True)[:15]

        for org in stores:
            if not org.id in org_id_to_props:
                org_id_to_props[org.id] = {'mean_price': None, 'example_pics': []}

        if not stores_inds_order and not final_try:
            return self.process(spellcheck(msg), final_try=True)

        res_type = 'intent' if intent_list else 'no_answer'
        res_type = 'promo' if 'promo' in intent_list else res_type
        res_type = 'prod' if prod_org_list else res_type
        res_type = 'name_kw' if name_kw_stores else res_type
        return stores_inds_order, org_id_to_props, list(intent_list.keys()), res_type


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
                    plan_image=row['map'],
                    store_image=row['store'],
                    bot=self.acur_bot,
                    is_availible_for_subscription=is_avail_for_subscr,
                    cat=store_cat,
                    be_in_link = row['input_url'],
                    is_top = row['top']=='top',
                    intent_list=row['intent_new'],
                    assort_kw =row['assort_kw'],
                    minus_words=row['minus_words'].replace('-', '')
            )

            await store.get_plan_pic_file_id(self.dp.bot)
            await asyncio.sleep(.5)
        await self.init_text_bot()

    async def init_text_bot(self):
        import pickle
        stores_list = await database_sync_to_async(Store.objects.filter)(bot=self.acur_bot)
        stores_list = await sync_to_async(list)(stores_list)

        text_bot = TextProcesser()
        self.model_api_url =self.bot_config['model_api_url']
        self.morpho_model_url = self.bot_config['morpho_model_url']

        text_bot.acur_api_url = self.model_api_url
        text_bot.morpho_api_url = self.morpho_model_url

        prods_df = pd.read_pickle('lamoda_df.pickle')

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
                row_template['id'] = uuid.uuid1()
                row_list.append(row_template)

        add_prods_df = pd.DataFrame(row_list)
        prods_df_enriched = prods_df.append(add_prods_df).reset_index().iloc[:, 1:]

        text_bot.prods_df_enriched = prods_df_enriched
        text_bot.prods_df_enriched = text_bot.prods_df_enriched.set_index('id')
        text_bot.wear_kws = pickle.load(open('wear_kws.pickle', 'rb'))

        #import pickle
        #pickle.dump(prod_name_to_indlist, open('prod_name_to_indlist.pickle', 'wb'))
        #pickle.dump(prods_df_enriched, open('prods_df_enriched.pickle', 'wb'))

        #text_bot.prod_name_to_indlist = pd.read_pickle('prod_name_to_indlist.pickle')
        #text_bot.prods_df_enriched = pd.read_pickle('prods_df_enriched.pickle')
        #cur_prod_df.shape[0]text_bot.in_2_label = pd.read_pickle('in_2_label.pkl')

        self.text_bot = text_bot
            # context.bot.send_media_group(chat_id=update.effective_chat.id, media=[inp_photo, inp_photo2])

    async def show_card(self, system_msg,org_id,plist_id):
        try:
            org = await database_sync_to_async(Store.objects.get)(pk=org_id, bot=self.acur_bot)
        except Store.DoesNotExist:
            return
        bot_user = await self.get_bot_user(system_msg.from_user)
        photo_id = await org.get_plan_pic_file_id(self.dp.bot)

        media = [InputMediaPhoto(media=photo_id,
                                 caption=org.get_card_text()[:MAX_CAPTION_SIZE],
                                 parse_mode='Markdown', )]
        try:
            plist = await database_sync_to_async(PictureList.objects.get)(pk=plist_id)
            pics_list = json.loads(plist.json_data)
        except PictureList.DoesNotExist:
            pics_list = []
        if pics_list:
            for photo_id in pics_list[:8]:
                media.append(InputMediaPhoto(photo_id))
        else:
            print('json.loads(org.pic_urls)[:8]',json.loads(org.pic_urls)[:8])
            for photo_id in json.loads(org.pic_urls)[:8]:
                media.append(InputMediaPhoto(photo_id))
        # await bot.send_media_group(message.from_user.id, media)
        bot_to_user_msg = await system_msg.answer_media_group(media)
        print(bot_to_user_msg[0].message_id)
        
    async def send_store_list(self,message, org_id_to_some_data, intent_list):
        text = "Возможно, вам подойдет:"
        keyboard = InlineKeyboardMarkup()

        org_id_list = list(org_id_to_some_data.keys())
        org_before_sorting = [(cur_org, org_id_list.index(cur_org.id)) for cur_org in self.text_bot.stores_list if
                              cur_org.id in org_id_to_some_data.keys()]
        stores_to_show = sorted(org_before_sorting, key=lambda x: x[1])
        stores_to_show = [obj for obj, ind in stores_to_show]

        lines_list = []
        for i, org in enumerate(stores_to_show):
            cur_title = org_id_to_some_data[org.id]['short_descr']
            lines_list += ["{}. {}".format(i + 1, cur_title)]
        text += '\n'
        text += ('\n').join(lines_list)

        keyboard_line_list = []
        for i, org in enumerate(stores_to_show):
            callback_dict = {'type': 'show_org',
                             'org_id': org.id,
                             'plist': org_id_to_some_data[org.id]['plit_id']}
            btn = InlineKeyboardButton(text=str(i + 1),
                                       callback_data=json.dumps(callback_dict))
            keyboard_line_list.append(btn)
            if i % 3 == 3 - 1:
                keyboard.row(*keyboard_line_list)
                keyboard_line_list = []
        if keyboard_line_list:
            keyboard.row(*keyboard_line_list)

        for intent_type in intent_list:
            if intent_type not in self.intent_to_name:
                continue
            btn_prev = InlineKeyboardButton(text="Все из категории " + self.intent_to_name[intent_type],
                                            callback_data=json.dumps(
                                                {'iten': intent_type,
                                                 'type': 'show_cat'}))
            keyboard.row(btn_prev)
        #btn_prev = InlineKeyboardButton(text="Связаться с оператором",
        #                                url='t.me/turbo_indus')
        #keyboard.row(btn_prev)
        await message.answer(text,
                            parse_mode="Markdown",
                             reply_markup=keyboard)



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
        self.model_api_url =self.bot_config['model_api_url']
        self.morpho_model_url = self.bot_config['morpho_model_url']



        # Configure logging
        logging.basicConfig(level=logging.DEBUG)
        bot = Bot(token=self.TOKEN)
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
            await self.init_text_bot()


        @self.dp.message_handler(commands=['start'])
        async def handle_welcome(message: types.Message):

            bot_user = await self.get_bot_user(message.from_user)
            await database_sync_to_async(bot_user.upd_last_active)()

            await database_sync_to_async(StartEvent.objects.create)(bot_user=bot_user, source=message.text.split('start')[-1])
            keyboard = InlineKeyboardMarkup()
            """org = await database_sync_to_async(Store.objects.filter)(title="Черная Пятница", bot=self.acur_bot)
            org = await sync_to_async(list)(org)
            # keyboard = []
            keyboard = InlineKeyboardMarkup()
            if org:
                org = org[0]
                callback_dict = {'type': 'show_org',
                                 'org_id': org.id,
                                 'plist': -100}
                btn = InlineKeyboardButton(text="Сокровища черной пятницы!",
                                           callback_data=json.dumps(callback_dict))
                keyboard.row(btn)"""

            await message.answer_photo(self.bot_config['welcome_photo_url'],
                                       caption=self.bot_config['welcome_text'][:MAX_CAPTION_SIZE],
                                       reply_markup=keyboard,
                                       parse_mode="Markdown")

            lotery_text = """🎁 Океания дарит подарки! 🎁
Только что у вас появился шанс выиграть один из двух сертификатов:

1️⃣ В немецкий магазин одежды FALKE, или...
2️⃣ В спортивный магазин Reebok! 

Выбирайте один из двух вариантов и участвуйте в конкурсе! Итоги подведем до 28.12.2020."""
            keyboard = InlineKeyboardMarkup()
            callback_dict = {'type': 'lotery_Falke'}
            btn = InlineKeyboardButton(text="1️⃣ Хочу сертификат FALKE!",
                                       callback_data=json.dumps(callback_dict))
            keyboard.row(btn)

            callback_dict = {'type': 'lotery_Reebok'}
            btn = InlineKeyboardButton(text="2️⃣ Хочу сертификат Reebok!",
                                       callback_data=json.dumps(callback_dict))
            keyboard.row(btn)


            btn = InlineKeyboardButton(text="Условия конкурса",
                                       url='https://www.google.com/')
            keyboard.row(btn)
            await message.answer(lotery_text,
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

            if message.text == 'удалить все':
                bot_users = await database_sync_to_async(BotUser.objects.filter)(bot=self.acur_bot)
                bot_users = await sync_to_async(list)(bot_users)
                #bot_user = await database_sync_to_async(BotUser.objects.get)(bot_user_id=str(from_user.id),
                #                                                             bot=self.acur_bot)
                for user in bot_users:
                    for i in range(20000,21000):
                        await asyncio.sleep(.1)
                        print(int(user.bot_user_id), int(i))
                        try:
                            await self.dp.bot.delete_message(int(user.bot_user_id), int(i))
                        except:
                            print('exception')
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


            org_list, org_id_to_props, intent_list, search_type = self.text_bot.process(message.text.replace('ё','е'))
            print('search_type', search_type)
            org_id_to_some_data = defaultdict(dict)
            for org in org_list:
                print(org.id ,'org.id')
                if org_id_to_props[org.id]['mean_price']:
                    org_id_to_some_data[org.id]['short_descr'] = org.get_inlist_descr(
                        "(~{} руб.)".format(int(org_id_to_props[org.id]['mean_price'])))
                else:
                    org_id_to_some_data[org.id]['short_descr'] = org.get_inlist_descr()
                pic_list = org_id_to_props[org.id]['example_pics']
                plit = await database_sync_to_async(PictureList.objects.create)(json_data=json.dumps(pic_list))
                org_id_to_some_data[org.id]['plit_id'] = plit.id

            if len(org_id_to_some_data)==1:
                await self.show_card(message,org.id,org_id_to_some_data[org.id]['plit_id'])
                repl_text, keyboard = await get_answer_by_lotery(search_type, bot_user)
                if repl_text:
                    await asyncio.sleep(5)
                    await message.answer(text=repl_text,reply_markup=keyboard,parse_mode="Markdown")

                return
            if not org_id_to_some_data:
                card = await database_sync_to_async(Store.objects.get)(intent_list='["no_answer"]',bot=self.acur_bot)
                await self.show_card(message, card.id, -1)
                repl_text, keyboard = await get_answer_by_lotery(search_type, bot_user)
                if repl_text:
                    await asyncio.sleep(5)
                    await message.answer(text=repl_text,reply_markup=keyboard,parse_mode="Markdown")
                return
            await self.send_store_list(message, org_id_to_some_data, intent_list)
            repl_text, keyboard = await get_answer_by_lotery(search_type, bot_user)
            if repl_text:
                await asyncio.sleep(5)
                await message.answer(text=repl_text, reply_markup=keyboard, parse_mode="Markdown")



        @self.dp.callback_query_handler()
        async def keyboard_callback_handler(callback: CallbackQuery):
            data = callback.data
            real_data = json.loads(data)

            bot_user = await self.get_bot_user(callback.from_user)
            await database_sync_to_async(bot_user.upd_last_active)()

            store_data = {k: v for k, v in real_data.items()}
            if store_data['type'] in ['show_org'] and 'org_id' in store_data:
                try:
                    org = await database_sync_to_async(Store.objects.get)(pk=store_data['org_id'], bot=self.acur_bot)
                except Store.DoesNotExist:
                    return
                store_data['org_name'] = org.title
                store_data['bot'] = self.acur_bot.username
            await database_sync_to_async(BtnPressedEvent.objects.create)(bot_user=bot_user, details_json=json.dumps(data))

            if real_data['type'] == 'operator':
                bot_user.is_operator_dicussing = True
                await database_sync_to_async(bot_user.save)()
                await callback.message.answer('Напишите запрос оператору:')
                return


            if real_data['type'] in ['show_org'] and 'org_id' in real_data:
                await self.show_card(callback.message,real_data['org_id'],real_data['plist'])

            if real_data['type'] in ['show_cat']:
                org_list =[org for org in self.text_bot.stores_list if real_data['iten'] in org.intent_list]
                org_id_to_some_data = defaultdict(dict)
                for org in sorted(org_list, key=lambda x: x.title):
                    org_id_to_some_data[org.id]['short_descr'] = org.get_inlist_descr()
                    plit = await database_sync_to_async(PictureList.objects.create)(json_data=json.dumps([]))
                    org_id_to_some_data[org.id]['plit_id'] = plit.id


                await self.send_store_list(callback.message, org_id_to_some_data, [])

            if real_data['type'] in ['lotery_Falke', 'lotery_Reebok', 'lotery_full']:
                repl_text, keyboard = await get_answer_by_lotery(real_data['type'], bot_user)
                if repl_text:
                    await callback.message.answer(repl_text, reply_markup=keyboard,parse_mode="Markdown")
                    return
            if real_data['type']=='finish_lotery':
                repl_text = """👏 Отлично, ваш шанс на победу удвоен! 👏

Напоминаем, итоги конкурса будут подведены до 28.12.2020 в этом чат-боте. 

Пользуйтесь чат-ботом и задавайте ему любые вопросы о ТРЦ, на многие он сможет ответить (или, по крайней мере, узнать, что вам интересно и ответить в следующей версии)!

 *Остаемся на связи!*

Будем рады узнать ваши комментарии, замечания и пожелания, это поможет нам стать лучше!
                """
                keyboard = InlineKeyboardMarkup()
                btn = InlineKeyboardButton(text="Дать обратную связь",
                                           url='https://forms.gle/kVu19uaroh99DDAT8')
                keyboard.row(btn)
                await callback.message.answer_photo('https://www.omni-academy.com/wp-content/uploads/2020/04/ROBOTIC-2-1-1-1-1-1-1-1-1-1-1-600x600.jpg',
                                           caption=repl_text,
                                           reply_markup = keyboard,
                                           parse_mode="Markdown")







        @self.dp.channel_post_handler(content_types=ContentTypes.ANY)
        async def my_channel_post_handler(message: types.Message):
            my_users = await database_sync_to_async(BotUser.objects.filter)( bot=self.acur_bot)
            my_users = await sync_to_async(list)(my_users)

            for bot_user in my_users:
                await message.forward(bot_user.bot_user_id)

        executor.start_polling(dp, skip_updates=True, on_startup=on_start,)