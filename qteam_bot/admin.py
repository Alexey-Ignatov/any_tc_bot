from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import BotUser, Store,StoreCategory,StartEvent, MessageLog,AcurBot

import json


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    pass
    #list_display= ('id','title', 'num_likes', 'num_dislikes',  'num_shows', 'is_active')


    #fields = ('title', 'num_likes')

@admin.register(StoreCategory)
class StoreCategoryAdmin(admin.ModelAdmin):
    pass

@admin.register(BotUser)
class BotUserAdmin(admin.ModelAdmin):
    list_display = ('id','bot_user_id', 'first_name', 'last_name', 'username', 'last_active', 'bot')
    ordering = ['-last_active']

@admin.register(StartEvent)
class StartEventAdmin(admin.ModelAdmin):
    pass

@admin.register(MessageLog)
class MessageLogAdmin(admin.ModelAdmin):
    list_display = ('id','bot_user', 'view_bot', 'text')

    def view_bot(self, obj):
        return obj.bot_user.bot



@admin.register(AcurBot)
class AcurBotAdmin(admin.ModelAdmin):
    pass

"""

@admin.register(CardCategory)
class CardCategoryAdmin(admin.ModelAdmin):
    pass

@admin.register(CardDate)
class CardDateAdmin(admin.ModelAdmin):
    pass


@admin.register(BookEveningEvent)
class BookEveningEventAdmin(admin.ModelAdmin):
    pass

@admin.register(CardLike)
class CardLikeAdmin(admin.ModelAdmin):
    pass

@admin.register(CardDislike)
class CardDislikeAdmin(admin.ModelAdmin):
    pass

@admin.register(BotUser)
class BotUserAdmin(admin.ModelAdmin):
    list_display = ('id','bot_user_id', 'first_name', 'last_name', 'username', 'last_active')
    ordering = ['-last_active']


@admin.register(BotUserToCardCategory)
class BotUserToCardCategoryAdmin(admin.ModelAdmin):
    pass


@admin.register(DateUserCardSet)
class DateUserCardSetAdmin(admin.ModelAdmin):
    pass

@admin.register(OpenCardEvent)
class OpenCardEventAdmin(admin.ModelAdmin):
    pass

@admin.register(GetCardsEvent)
class GetCardsEventAdmin(admin.ModelAdmin):
    pass

@admin.register(GetPlansEvent)
class GetPlansEventAdmin(admin.ModelAdmin):
    pass

@admin.register(StartEvent)
class StartEventAdmin(admin.ModelAdmin):
    pass

"""