from django.shortcuts import render

# Create your views here.
from django.http import HttpResponse
import datetime
from rest_framework import authentication, permissions
from rest_framework import routers, serializers, viewsets

from django.contrib.auth.models import User, Group
from rest_framework import viewsets
from .serializers import UserSerializer, GroupSerializer, CardSerializer, BotUserSerializer
from .models import Card, CardLike, CardDislike,BotUser,BotUserToCardCategory, CardCategory,BookEveningEvent,CardDate,DateUserCardSet
from rest_framework.response import Response
from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes
from django.db import transaction
from django.http import Http404
from rest_framework.exceptions import ValidationError
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django.utils import timezone
import json
import requests
from random import shuffle
import time

dayno_2_dayname = {
    0: "Понедельник",
    1: "Вторник",
    2: "Среда",
    3: "Четверг",
    4: "Пятница",
    5: "Суббота",
    6: "Воскресенье"

}

datetime.datetime.strptime("2019-01-01", "%Y-%m-%d").date()
dates_on_btns_num = 7

def get_cards_ok_to_show(individual_stop_list=[]):
    horizont_date = (timezone.now() + datetime.timedelta(days=7) + datetime.timedelta(hours=3)).date()
    curr_date = (timezone.now() + datetime.timedelta(hours=3)).date()

    good_period_cards = Card.objects.filter(is_active=True,
                                         date_starts__lte=curr_date,
                                         date_ends__gte=horizont_date,
                                         is_special_dates = False)

    good_carddates = CardDate.objects.filter(date__lte=horizont_date, date__gte=curr_date)
    special_date_cards_set = set([card_date.card for card_date in good_carddates])
    res_set = ( special_date_cards_set | set(good_period_cards)) - set(individual_stop_list)

    return list(res_set)


def get_cards_ok_to_show_on_date(date,individual_stop_list=[]):

    good_period_cards = Card.objects.filter(is_active=True,
                                            date_starts__lte=date,
                                            date_ends__gte=date,
                                            is_special_dates=False)

    good_carddates = CardDate.objects.filter(date=date, card__is_active=True)
    special_date_cards_set = set([card_date.card for card_date in good_carddates])
    res_set = (special_date_cards_set | set(good_period_cards)) - set(individual_stop_list)

    return list(res_set)



def upd_resp_path(bot_user, resp_path):
    bot_user.main_resp_path = resp_path
    bot_user.save()


def get_card_message_telegram_req(card, date_dict =None,likes_btns=True):
    text ="*{}* \n{}".format(card.title, card.card_text)

    btns_lines = []
    if likes_btns:
        likes_btns =[
            {"text": "👍",
             "callback_data": json.dumps({'card_id': card.id, 'type': 'like'})},
            {"text": "👎",
             "callback_data": json.dumps({'card_id': card.id, 'type': 'dislike'})}
        ]
        btns_lines.append(likes_btns)
    if date_dict:
        book_btns = [
            {'text': "✅ В план на {}".format(date_dict['date_text']), "callback_data": json.dumps({'card_id': card.id, 'date': str(date_dict['date']), 'type':'book'})}
        ]
        btns_lines.append(book_btns)

    return {"text":text,
            "parse_mode": "Markdown",
            "reply_markup": {"inline_keyboard":btns_lines}}


def get_date_btns(card, bot_user, card_dates):
    print('card_dates', card_dates)
    btns_list = []
    #for cat in cats:
    #    btns_list.append([{'text': cat.title, "callback_data": json.dumps({'cat_id': cat.id, 'action': 'on'})}])

    for i in range(dates_on_btns_num):
        i_datetime = (timezone.now() + datetime.timedelta(days=i)+ datetime.timedelta(hours=3)).date()
        if card.is_special_dates:
            print('i_datetime', i_datetime)
            print('card_dates', card_dates)
            if i_datetime not in card_dates:
                continue
        text = dayno_2_dayname[i_datetime.weekday()] + ', ' + str(i_datetime.strftime("%d.%m"))
        text = 'Сегодня'+ ', ' + str(i_datetime.strftime("%d.%m")) if i == 0 else text
        text = 'Завтра' + ', ' + str(i_datetime.strftime("%d.%m")) if i == 1 else text
        if i in [0, 1] \
                or i_datetime.weekday() in [4, 5, 6] \
                or card.is_special_dates:
            #TODO тут сохраняется время по таймзоне на сервере
            btns_list.append([{'text': text, "callback_data": json.dumps({'card_id': card.id, 'date': str(i_datetime), 'type':'book'})}])
    return btns_list



def date_to_date_dict(date):
    curr_time = timezone.now() + datetime.timedelta(hours=3)

    text = dayno_2_dayname[date.weekday()] + ', ' + str(date.strftime("%d.%m"))
    text = 'Сегодня' + ', ' + str(date.strftime("%d.%m")) if curr_time.date() == date else text
    text = 'Завтра' + ', ' + str(date.strftime("%d.%m")) if (curr_time + datetime.timedelta(days=1)).date() == date else text
    return {'date':date, 'date_text':text}

def get_next_weekend_and_names():
    res_list = []
    curr_time = timezone.now() + datetime.timedelta(hours=3)
    for i in range(7):
        i_date = (curr_time + datetime.timedelta(days=i)).date()
        if i_date.weekday() not in [4, 5, 6]:
            continue

        res_list.append(date_to_date_dict(i_date))
    return res_list




def index(request):
    return HttpResponse("Hello, world. You're at the polls index.")

class UserViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = User.objects.all().order_by('-date_joined')
    serializer_class = UserSerializer

class GroupViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows groups to be viewed or edited.
    """
    queryset = Group.objects.all()
    serializer_class = GroupSerializer

class CardViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows groups to be viewed or edited.
    """
    queryset = Card.objects.all()
    serializer_class = CardSerializer

# Wire up our API using automatic URL routing.
# Additionally, we include login URLs for the browsable API.

class UpdPrefsApi(APIView):

    @staticmethod
    def put(request, bot_user_id):
        print(request.data)
        real_data = json.loads(request.data['str_to_parse'])
        resp_path = request.data['resp_path']
        try:
            bot_user = BotUser.objects.get(bot_user_id=bot_user_id)
        except BotUser.DoesNotExist:
            bot_user = BotUser.objects.create(bot_user_id=bot_user_id)


        upd_resp_path(bot_user, resp_path)

        try:
            cat = CardCategory.objects.get(pk=real_data['cat_id'])
        except CardCategory.DoesNotExist:
            raise Http404

        try:
            user_cats = BotUserToCardCategory.objects.get(bot_user=bot_user, card_category=cat)
            if real_data['action'] == 'off':
                user_cats.delete()
        except BotUserToCardCategory.DoesNotExist:
            if real_data['action'] == 'on':
                BotUserToCardCategory.objects.create(bot_user=bot_user, card_category=cat)

        return Response({})

class ResetPrefsApi(APIView):

    @staticmethod
    def get(request, bot_user_id):
        try:
            bot_user = BotUser.objects.get(bot_user_id=bot_user_id)
        except BotUser.DoesNotExist:
            bot_user = BotUser.objects.create(bot_user_id=bot_user_id)

        resp_path = request.GET['resp_path']
        upd_resp_path(bot_user, resp_path)

        BotUserToCardCategory.objects.filter(bot_user = bot_user).delete()

        return Response({})


class LikeApi(APIView):

    @staticmethod
    def post(request, bot_user_id):
        print('real_data', request.data)
        real_data = json.loads(request.data['str_to_parse'])
        resp_path = request.data['resp_path']
        print('real_data', real_data)
        try:
            bot_user = BotUser.objects.get(bot_user_id=bot_user_id)
        except BotUser.DoesNotExist:
            bot_user = BotUser.objects.create(bot_user_id=bot_user_id)


        upd_resp_path(bot_user, resp_path)

        try:
            card = Card.objects.get(pk=real_data['card_id'])
        except Card.DoesNotExist:
            raise Http404

        if real_data['type'] == 'like':
            CardLike.objects.create(bot_user=bot_user, date=timezone.now()+ datetime.timedelta(hours=3), card = card )

        if real_data['type'] == 'dislike':
            CardDislike.objects.create(bot_user=bot_user, date=timezone.now()+ datetime.timedelta(hours=3), card = card)


        card_dates = [card_date.date for card_date in CardDate.objects.filter(card = card)]
        btns_list = get_date_btns(card, bot_user, card_dates)
        return Response({"btns_json": json.dumps(btns_list)})
        #return Response({"time":})


class BookEveningApi(APIView):
    @staticmethod
    def post(request, bot_user_id):
        real_data = json.loads(request.data['str_to_parse'])
        resp_path = request.data['resp_path']

        date = datetime.datetime.strptime(real_data['date'], "%Y-%m-%d").date()
        print('date', 'date')
        try:
            bot_user = BotUser.objects.get(bot_user_id=bot_user_id)
        except BotUser.DoesNotExist:
            bot_user = BotUser.objects.create(bot_user_id=bot_user_id)

        upd_resp_path(bot_user, resp_path)

        try:
            card = Card.objects.get(pk=real_data['card_id'])
        except Card.DoesNotExist:
            raise Http404


        try:
            BookEveningEvent.objects.get(bot_user=bot_user, card=card, planed_date=date)
        except BookEveningEvent.DoesNotExist:
            BookEveningEvent.objects.create(bot_user=bot_user, card=card, planed_date=date)


        return Response({})
        #return Response({"time":})




class RegisterUser(APIView):
    @staticmethod
    def post(request, bot_user_id):
        try:
            bot_user = BotUser.objects.get(bot_user_id=bot_user_id)
        except BotUser.DoesNotExist:
            bot_user = BotUser.objects.create(bot_user_id=bot_user_id)

        resp_path = request.data['resp_path']
        print('resp_path', resp_path)
        upd_resp_path(bot_user, resp_path)

        data_to_validate = request.data

        print(request.data)
        #data_to_validate['cashbox'] = device_id
        return Response({})


class GetMyStrCategories(APIView):
    @staticmethod
    def get(request, bot_user_id):
        meta = request.META
        try:
            bot_user = BotUser.objects.get(bot_user_id=bot_user_id)
        except BotUser.DoesNotExist:
            bot_user = BotUser.objects.create(bot_user_id=bot_user_id)

        resp_path = request.GET['resp_path']
        print('resp_path', resp_path)
        upd_resp_path(bot_user, resp_path)

        user_cats = BotUserToCardCategory.objects.filter(bot_user = bot_user)

        res_list = [user_2_cat.card_category.title for user_2_cat in user_cats]

        print(request.data)
        res_str = ', '.join(res_list) if res_list else "Ни одной категории не выбрано"

        return Response({"user_cats":res_str})


class GetCatButtonsList(APIView):
    @staticmethod
    def get(request, bot_user_id):
        meta = request.META
        try:
            bot_user = BotUser.objects.get(bot_user_id=bot_user_id)
        except BotUser.DoesNotExist:
            bot_user = BotUser.objects.create(bot_user_id=bot_user_id)

        resp_path = request.GET['resp_path']
        print('resp_path', resp_path)
        upd_resp_path(bot_user, resp_path)


        btns_list = []
        cats = CardCategory.objects.all()
        for cat in cats:
            btns_list.append([{'text':cat.title, "callback_data":json.dumps({'cat_id':cat.id, 'action':'on'})}])

        btns_list+=[[{"text":"Посмотреть мои категории", "callback_data":"{\"show_cats\":true}"}],
                    [{"text":"❌ Сбросить категории ❌","callback_data":"reset cats"}]]

        return Response({"btns_json": json.dumps(btns_list)})


class SendFreeEveningReminderApi(APIView):

    @staticmethod
    def get(request):
        url = "https://flowxo.com/hooks/a/d678bypz"
        curr_date = (timezone.now() + datetime.timedelta(hours=3)).date()
        today_book_events = BookEveningEvent.objects.filter(planed_date=curr_date)
        for event in today_book_events:
            curr_bot_user = event.bot_user
            curr_card = event.card
            #todo use get_telega_req
            send_data = {'text':"Дорогой друг! Освободи вечер, у тебя сегодня: "+ curr_card.title ,
                         "resp_path": curr_bot_user.main_resp_path,
                         'card':CardSerializer(curr_card).data}

            response = requests.post(url, json=send_data)

        return Response({})
        #return Response({"time":})


##todo add card check
class SendAddActivityApi(APIView):

    @staticmethod
    def get(request):
        url = "https://flowxo.com/hooks/a/2m8bd4q9"
        curr_date = (timezone.now() + datetime.timedelta(hours=3)).date()
        today_book_events = list(BookEveningEvent.objects.filter(planed_date__gte=curr_date))

        users = list(set([event.bot_user for event in today_book_events]))
        resppath_2_card_list ={bot_user.bot_user_id:[event.card for event in today_book_events if bot_user==event.bot_user]
                for bot_user in users}

        print('resppath_2_card_list', resppath_2_card_list)


        for bot_user_id, future_card_list in resppath_2_card_list.items():
            # todo
            if len(future_card_list) < 2:
                cards_liks = CardLike.objects.filter(bot_user__bot_user_id=bot_user_id).order_by('?')
                liked_cards = list(set([cl.card for cl in cards_liks])- set(future_card_list))

                possible_cards = get_cards_ok_to_show()
                cards_to_show = [card for card in liked_cards if card in possible_cards]
                print('SendAddActivityApi: cards', cards_to_show)
                bot_user = BotUser.objects.get(bot_user_id=bot_user_id)

                send_data = {"resp_path": bot_user.main_resp_path,
                             'cards':CardSerializer(cards_to_show[:3], many=True).data}

                print('send_data', send_data)

                response = requests.post(url, json=send_data)

        return Response({})
        #return Response({"time":})


class GetWeekPlansApi(APIView):

    @staticmethod
    def get(request, bot_user_id):
        meta = request.META
        try:
            bot_user = BotUser.objects.get(bot_user_id=bot_user_id)
        except BotUser.DoesNotExist:
            bot_user = BotUser.objects.create(bot_user_id=bot_user_id)

        resp_path = request.GET['resp_path']
        upd_resp_path(bot_user, resp_path)

        curr_date = (timezone.now() + datetime.timedelta(hours=3)).date()
        today_book_events = list(BookEveningEvent.objects.filter(planed_date__gte=curr_date, bot_user = bot_user).order_by('planed_date'))

        print('today_book_events', today_book_events)

        resp_list = []
        for book_event in today_book_events:
            text_date = dayno_2_dayname[book_event.planed_date.weekday()] + ', ' + str(book_event.planed_date.strftime("%d.%m"))
            if book_event.planed_date == (timezone.now() + datetime.timedelta(days=1) + datetime.timedelta(hours=3)).date():
                text_date = "Завтра"

            if book_event.planed_date == (timezone.now()+datetime.timedelta(hours=3)).date():
                text_date = "Сегодня"

            resp_list.append({
                'card': CardSerializer(book_event.card).data,
                'date':text_date
            })


        return Response({'resp_data':resp_list})
        #return Response({"time":})




class GetCardsApi(APIView):

    @staticmethod
    def get(request, bot_user_id):
        meta = request.META
        try:
            bot_user = BotUser.objects.get(bot_user_id=bot_user_id)
        except BotUser.DoesNotExist:
            bot_user = BotUser.objects.create(bot_user_id=bot_user_id)

        resp_path = request.GET['resp_path']
        upd_resp_path(bot_user, resp_path)

        try:
            date_user_card_set = DateUserCardSet.objects.get(bot_user=bot_user, date=(datetime.datetime.now() + datetime.timedelta(hours=3)).date())
            card_id_list = json.loads(date_user_card_set.card_ids)
            res_cards = Card.objects.filter(pk__in=card_id_list)
            #serializer = CardSerializer(res_cards, many=True)
            print("print from try")
            #return Response(serializer.data)
            return Response({"telegram_req":[get_card_message_telegram_req(card) for card in res_cards],
                             'req_count': len(res_cards) })
        except DateUserCardSet.DoesNotExist:
            pass
            #bot_user = DateUserCardSet.objects.create(bot_user_id=bot_user_id)

        #user_cats = BotUserToCardCategory.objects.filter(bot_user = bot_user)
        #if len(user_cats) < 3:
        #    return Response({'answer': 'less 3 cats'})

        liked_cards = [like.card for like in CardLike.objects.filter(bot_user=bot_user)]
        disliked_cards = [like.card for like in CardDislike.objects.filter(bot_user=bot_user)]

        res_cards = get_cards_ok_to_show(individual_stop_list=liked_cards+disliked_cards)

        shuffle(res_cards)
        res_cards = res_cards[:5]

        res_cards_ids = [card.id for card in res_cards]
        DateUserCardSet.objects.create(bot_user=bot_user, date=(datetime.datetime.now() + datetime.timedelta(hours=3)).date(), card_ids=json.dumps(res_cards_ids))


        #serializer = CardSerializer(res_cards, many=True)
        #return Response(serializer.data)

        return Response({"telegram_req":[get_card_message_telegram_req(card) for card in res_cards],
                         'req_count': len(res_cards) })







#class GetCardsTestWebhookSenderApi(APIView):
class GetCardsTestWebhookSenderApi(APIView):

    @staticmethod
    def get(request):
        url = "https://flowxo.com/hooks/a/vbd5q5wp"

        cards_list = Card.objects.all()
        resp_paths = ['5e55159e2b23da3ecf879abf/c/733585869', '5e55159e2b23da3ecf879abf/c/387056923']
        print('cards_list', cards_list)
        for card in cards_list:
            card.title += ' id:'+ str(card.id)
            for resp_path in resp_paths:
                send_data = {"resp_path": resp_path,
                             'cards': CardSerializer([card], many=True).data}

                print('send_data', send_data)

                response = requests.post(url, json=send_data)
            time.sleep(2)

        return Response({})
        # return Response({"time":})



class GetWeekendSchedule(APIView):

    @staticmethod
    def get(request, bot_user_id):
        try:
            bot_user = BotUser.objects.get(bot_user_id=bot_user_id)
        except BotUser.DoesNotExist:
            bot_user = BotUser.objects.create(bot_user_id=bot_user_id)

        resp_path = request.GET['resp_path']
        upd_resp_path(bot_user, resp_path)


        dates_list = get_next_weekend_and_names()
        print(dates_list)

        emodzi_list = ["🍕","️💥","🔥","🧠","👻",
                       "👌","🥋","🎣","⛳","️🎱","🏋",
                       "️‍️🛹","🥌","🥁","🎼","🎯","🎳",
                       "🎮","🎲","🏁","💡","🎪","🏏",
                       "🌪","🍿","🏄","‍️🎉","🧨","🎈"]
        shuffle(emodzi_list)

        plans_by_date = []
        btns_list = []
        final_text = ''.join(emodzi_list[:3])+"*Ваши планы на ближайшие выходные:*\n\n"
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

            final_text += '*{}*'.format("🗓" + curr_plan['date_text'] + ": ") + (curr_plan['plans_text'] if curr_plan['plans_text'] \
                                                            else "Ничего не запланировано") + '\n\n'

            btns_list.append([{'text': "🔎 "+ curr_plan['date_text'],
                               "callback_data": json.dumps({'type':"get_on_date", 'date': str(curr_plan['date'])})}])


        # plans_by_date to text

        final_text += "\nНажмите кнопку, чтобы получить активности на дату!"


        return Response({
                        "text": final_text,
                        "parse_mode": "Markdown",
                        "reply_markup": {
                                "inline_keyboard": btns_list

                            }
                        })


#def get

def get_cards_set_summary_telegram_req(cards_list, date_dict):
    text = date_dict['date_text'] + " Выберете развлечение для более подробного просмотра"

    btns_lines =[]
    for card in cards_list:
        btns_lines.append(
            [{"text": card.title,
              "callback_data": json.dumps({'card_id': card.id, 'type': 'show', 'date':str(date_dict['date'])})}]
        )

    return {"text":text,
            "parse_mode": "Markdown",
            "reply_markup": {"inline_keyboard":btns_lines}}


class GetCardsOnDateApi(APIView):

    @staticmethod
    def get(request, bot_user_id):
        real_data = json.loads(request.data['str_to_parse'])
        resp_path = request.GET['resp_path']

        date = datetime.datetime.strptime(real_data['date'], "%Y-%m-%d").date()
        print('date', date)
        try:
            bot_user = BotUser.objects.get(bot_user_id=bot_user_id)
        except BotUser.DoesNotExist:
            bot_user = BotUser.objects.create(bot_user_id=bot_user_id)

        upd_resp_path(bot_user, resp_path)

        liked_cards = [like.card for like in CardLike.objects.filter(bot_user=bot_user)]
        disliked_cards = [like.card for like in CardDislike.objects.filter(bot_user=bot_user)]

        res_cards = get_cards_ok_to_show_on_date(date,individual_stop_list=liked_cards+disliked_cards)

        shuffle(res_cards)
        res_cards = res_cards[:5]

        #return Response({"telegram_req":[get_card_message_telegram_req(card) for card in res_cards],
        #                 'req_count': len(res_cards) })
        return Response({"telegram_req":get_cards_set_summary_telegram_req(res_cards, date_dict=date_to_date_dict(date))})




class GetCertainCardApi(APIView):

    @staticmethod
    def get(request, bot_user_id):
        real_data = json.loads(request.data['str_to_parse'])
        resp_path = request.GET['resp_path']


        card_id = real_data['card_id']
        date = datetime.datetime.strptime(real_data['date'], "%Y-%m-%d").date()

        try:
            bot_user = BotUser.objects.get(bot_user_id=bot_user_id)
        except BotUser.DoesNotExist:
            bot_user = BotUser.objects.create(bot_user_id=bot_user_id)

        upd_resp_path(bot_user, resp_path)

        try:
            card = Card.objects.get(pk=card_id)
        except Card.DoesNotExist:
            raise Http404



        return Response({"telegram_req":[get_card_message_telegram_req(card,date_dict=date_to_date_dict(date))],
                         'req_count': 1 })

