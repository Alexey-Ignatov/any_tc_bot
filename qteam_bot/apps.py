from django.apps import AppConfig

from aiogram import Bot
from telegram.utils.request import Request


class QteamBotConfig(AppConfig):
    name = 'qteam_bot'

    def ready(self):
        # Singleton utility
        # We load them here to avoid multiple instantiation across other
        # modules, that would take too much time.
        from django.conf import settings
        from qteam_bot.models import AcurBot
        from telegram import Bot

        self.botid_to_botobj = {}
        # intent_model
        bots = AcurBot.objects.all()
        for bot in bots:
            request = Request(
                connect_timeout=0.5,
                read_timeout=1.0,
            )
            bot_obj = Bot(
                request=request,
                token=bot.token,
                base_url=getattr(settings, 'PROXY_URL', None),
            )



            self.botid_to_botobj[bot.telegram_bot_id] =bot_obj






