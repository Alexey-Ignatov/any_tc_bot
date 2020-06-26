from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from asgiref.sync import sync_to_async, async_to_sync
# Create your views here.

from django.apps import apps
from .models import InterBotMsg, BotUser,UserToOperatorMsgList



class SendMessageApi(APIView):
    @staticmethod
    def post(request):
        text = request.data['text']
        sender_user_id = str(request.data['sender_user_id'])
        to_teleg_bot_id = str(request.data['to_teleg_bot_id'])
        user_to_bot_msg_id = str(request.data['user_to_bot_msg_id'])
        receiver_user_id = str(request.data['receiver_user_id'])
        from_teleg_bot_id =  str(request.data['from_teleg_bot_id'])
        reply_to = int(request.data['reply_to']) if request.data['reply_to'] else None


        bot_to_user_msg = apps.get_app_config('qteam_bot').botid_to_botobj[to_teleg_bot_id]\
            .send_photo(chat_id=int(receiver_user_id),photo ='https://gallery.kissclipart.com/20180829/gaw/kissclipart-customer-support-icon-blue-clipart-customer-servic-4764cde0bb24edf6.jpg',
                        caption=text, reply_to_message_id=reply_to)


        sender_bot_user = BotUser.objects.get(bot__telegram_bot_id=from_teleg_bot_id,bot_user_id=sender_user_id )
        receiver_bot_user = BotUser.objects.get(bot__telegram_bot_id=to_teleg_bot_id,bot_user_id=receiver_user_id )
        print('SendMessageApi: before send')


        InterBotMsg.objects.create( bot_to_receiver_msg_id = bot_to_user_msg.message_id,
                                   sender_to_bot_msg_id = user_to_bot_msg_id,
                                   text = text,
                                   sender_bot_user = sender_bot_user,
                                   receiver_bot_user = receiver_bot_user)

        return Response({})


class MessageToOperatorApi(APIView):
    @staticmethod
    def post(request):
        text = request.data['text']
        sender_user_id = str(request.data['sender_user_id'])
        to_teleg_bot_id = str(request.data['to_teleg_bot_id'])
        user_to_bot_msg_id = str(request.data['user_to_bot_msg_id'])
        from_teleg_bot_id = str(request.data['from_teleg_bot_id'])

        sender_bot_user = BotUser.objects.get(bot__telegram_bot_id=from_teleg_bot_id, bot_user_id=sender_user_id)
        admins_list = BotUser.objects.filter(bot__telegram_bot_id = to_teleg_bot_id, is_operator = True)

        user_to_operator_msg = UserToOperatorMsgList.objects.create(
                                       sender_to_bot_msg_id=user_to_bot_msg_id,
                                       text=text,
                                       sender_bot_user=sender_bot_user,)
        for admin_bot_user in admins_list:
            bot_to_user_msg = apps.get_app_config('qteam_bot').botid_to_botobj[to_teleg_bot_id].send_message(int(admin_bot_user.bot_user_id), text=text)

            InterBotMsg.objects.create(bot_to_receiver_msg_id=bot_to_user_msg.message_id,
                                       sender_to_bot_msg_id=user_to_bot_msg_id,
                                       text=text,
                                       sender_bot_user=sender_bot_user,
                                       receiver_bot_user=admin_bot_user,
                                       user_to_operator_msg_list=user_to_operator_msg)









        return Response({})