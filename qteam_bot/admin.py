from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import Card, CardLike, CardDislike,BotUser,BotUserToCardCategory, CardCategory,BookEveningEvent,CardDate,DateUserCardSet
from .models import OpenCardEvent, GetCardsEvent,GetPlansEvent,StartEvent
import json
from .views import get_cards_ok_to_show_on_date,get_next_weekend_and_names

@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    list_display= ('id','title', 'num_likes', 'num_dislikes',  'num_shows', 'is_active','is_available_now')


    def num_likes(self, obj):
        likes = CardLike.objects.filter(card=obj)
        return len(set([like.bot_user for like in likes]))

    def num_dislikes(self, obj):
        likes = CardDislike.objects.filter(card=obj)
        return len(set([like.bot_user for like in likes]))

    def num_shows(self, obj):
        sets = DateUserCardSet.objects.all()
        return len([True for el in sets if obj.id in json.loads(el.card_ids)])

    def is_available_now(self, obj):
        weekends = get_next_weekend_and_names()
        for date_dict in weekends:
            if obj in get_cards_ok_to_show_on_date(date=date_dict['date']):
                return True

        return False

    is_available_now.boolean = True
    #fields = ('title', 'num_likes')






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
    list_display = ('bot_user_id', 'first_name', 'last_name', 'username', 'last_active')
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

