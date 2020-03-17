from django.db import models

# Create your models here.
from django.db import models

# Create your models here.
from django.db import models
import json
from django.utils import timezone
import datetime

class CardCategory(models.Model):
    title = models.CharField(max_length=200)
    def num_likes(self, obj):
        likes = CardLike.objects.filter(card=self)
        return len(set([like.bot_user for like in likes]))

    def __str__(self):
        return self.title


class Card(models.Model):
    is_active = models.BooleanField(default=True)
    is_special_dates = models.BooleanField(default=False)
    title = models.CharField(max_length=200)
    card_text = models.TextField(max_length=2000)
    card_cat = models.ForeignKey(CardCategory, on_delete=models.CASCADE)

    date_starts = models.DateField()
    date_ends = models.DateField()

    image = models.ImageField(null=True)
    pic_file_id = models.CharField(max_length=300,default='')


    def __str__(self):
        return self.title


class CardDate(models.Model):
    card = models.ForeignKey(Card, on_delete=models.CASCADE)
    date = models.DateField()

    def __str__(self):
        return self.card.title + " " + str(self.date)

class BotUser(models.Model):
    bot_user_id  = models.CharField(max_length=100)
    main_resp_path = models.CharField(max_length=100)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    username = models.CharField(max_length=100)

    last_active = models.DateTimeField()
    def upd_last_active(self):
        self.last_active = timezone.now()
        self.save()


    def __str__(self):
        return str(self.id) + ' '+  str(self.bot_user_id)


class BotUserToCardCategory(models.Model):
    bot_user = models.ForeignKey(BotUser, on_delete=models.CASCADE)
    card_category = models.ForeignKey(CardCategory, on_delete=models.CASCADE)

    def __str__(self):
        return str(self.bot_user.bot_user_id) + self.card_category.title


class CardLike(models.Model):
    bot_user = models.ForeignKey(BotUser, on_delete=models.CASCADE)
    card = models.ForeignKey(Card, on_delete=models.CASCADE)
    date = models.DateField()

    def __str__(self):
        return self.card.title


class CardDislike(models.Model):
    bot_user = models.ForeignKey(BotUser, on_delete=models.CASCADE)
    card = models.ForeignKey(Card, on_delete=models.CASCADE)
    date = models.DateField()

    def __str__(self):
        return self.card.title

class BookEveningEvent(models.Model):
    bot_user = models.ForeignKey(BotUser, on_delete=models.CASCADE)
    card = models.ForeignKey(Card, on_delete=models.CASCADE)
    planed_date = models.DateField()

    def __str__(self):
        return self.card.title


class DateUserCardSet(models.Model):
    bot_user = models.ForeignKey(BotUser, on_delete=models.CASCADE)
    card_ids = models.CharField(max_length=300, default=json.dumps([]))
    date = models.DateField()

    def __str__(self):
        return str(self.bot_user.bot_user_id) + ' ' + self.card_ids




class OpenCardEvent(models.Model):
    bot_user = models.ForeignKey(BotUser, on_delete=models.CASCADE)
    card = models.ForeignKey(Card, on_delete=models.CASCADE)
    date_added = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return str(self.bot_user.bot_user_id) + ' ' + str(self.date_added)


class GetCardsEvent(models.Model):
    bot_user = models.ForeignKey(BotUser, on_delete=models.CASCADE)
    date_added = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return str(self.bot_user.bot_user_id) + ' ' + str(self.date_added)

class GetPlansEvent(models.Model):
    bot_user = models.ForeignKey(BotUser, on_delete=models.CASCADE)
    date_added = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return str(self.bot_user.bot_user_id) + ' ' + str(self.date_added)

class StartEvent(models.Model):
    bot_user = models.ForeignKey(BotUser, on_delete=models.CASCADE)
    date_added = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return str(self.bot_user.bot_user_id) + ' ' + str(self.date_added)