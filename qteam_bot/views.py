from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from asgiref.sync import sync_to_async, async_to_sync
# Create your views here.

from django.apps import apps



class SendMessageApi(APIView):
    @staticmethod
    def post(request):
        text = request.data['text']
        teleg_bot_id = str(request.data['teleg_bot_id'])
        apps.get_app_config('qteam_bot').botid_to_botobj[teleg_bot_id].send_message(int(request.data['telegram_user_id']), text=text)

        return Response({})

