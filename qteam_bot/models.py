from django.db import models

# Create your models here.
from django.db import models

# Create your models here.
from django.db import models
import json
from django.utils import timezone
from django.conf import settings
import datetime
from channels.db import database_sync_to_async






class StoreCategory(models.Model):
    title = models.CharField(max_length=200)

    def __str__(self):
        return self.title


class AcurBot(models.Model):
    token = models.CharField(max_length=200)

    telegram_bot_id = models.CharField(max_length=200)
    first_name = models.CharField(max_length=200)
    username = models.CharField(max_length=200)


    def __str__(self):
        return self.username



class Store(models.Model):
    bot = models.ForeignKey(AcurBot, on_delete=models.DO_NOTHING)

    is_active = models.BooleanField(default=True)

    title = models.CharField(max_length=200)
    short_descr = models.CharField(max_length=1000)
    long_descr = models.CharField(max_length=2000)
    alter_names = models.CharField(max_length=1000, default='')

    brand = models.CharField(max_length=200)
    keywords = models.TextField(max_length=2000)
    cat = models.ForeignKey(StoreCategory, on_delete=models.DO_NOTHING)
    floor = models.CharField(max_length=200)
    phone_number = models.CharField(max_length=200)

    plan_image = models.ImageField(null=True)
    store_image = models.ImageField(null=True)
    plan_pic_file_json = models.CharField(max_length=100000, default=json.dumps({}))
    store_pic_file_json = models.CharField(max_length=100000, default=json.dumps({}))

    is_availible_for_subscription = models.BooleanField(default=True)


    def get_card_text(self):
        res_text = "*{}*".format(self.title)
        if not self.is_active:
            res_text += " (временно закрыт)"
        if self.floor:
            res_text += "\nЭтаж: {}".format(self.floor)
        #if self.phone_number:
        #    res_text += "\nТелефон: {}".format(self.phone_number)
        if self.long_descr:
            res_text += "\n{}".format(self.long_descr)
        return res_text

    def get_inlist_descr(self):
        res_text = "*{}*".format(self.title)
        if not self.is_active:
            res_text += " (временно закрыт)"
        if self.short_descr:
            res_text += ": {}".format(self.short_descr)
        return res_text

    def get_token(self):
        return self.bot.token

    async def get_plan_pic_file_id(self, bot):
        if not self.plan_image.url:
            return None
        print('get_plan_pic_file_id not none')
        print('self.plan_pic_file_json', self.plan_pic_file_json)
        # todo тут хорошо бы проверять не имя, а хэш картинки
        token_to_file_dict = json.loads(self.plan_pic_file_json)
        print('token_to_file_dict', token_to_file_dict)
        token = await database_sync_to_async(self.get_token)()

        if token in token_to_file_dict:
            url = token_to_file_dict[token]['image_url']
            if url == self.plan_image.url:
                return token_to_file_dict[token]['telegr_file_id']

        print('after if')
        print('settings.BASE_DIR + self.plan_image.url', settings.BASE_DIR + self.plan_image.url)
        with open(settings.BASE_DIR + self.plan_image.url, 'rb') as f:
            print('in_with')
            msg = await bot.send_photo(646380871, f)
        print('after if')
        token_to_file_dict[token] = {'image_url':self.plan_image.url,
                                              'telegr_file_id':msg.photo[0].file_id}

        self.plan_pic_file_json = json.dumps(token_to_file_dict)
        await database_sync_to_async(self.save)()
        return token_to_file_dict[token]['telegr_file_id']

    def get_store_pic_file_id(self, bot):
        if not self.store_image.url:
            return None
        print('get_store_pic_file_id not none')
        # todo тут хорошо бы проверять не имя, а хэш картинки
        token_to_file_dict = json.loads(self.store_pic_file_json)
        if self.bot.token in token_to_file_dict:
            url = token_to_file_dict[self.bot.token]['image_url']
            if url == self.store_image.url:
                return token_to_file_dict[self.bot.token]['telegr_file_id']

        with open(settings.BASE_DIR + self.store_image.url, 'rb') as f:
            print('in_with')
            msg = bot.send_photo(646380871, f)

        token_to_file_dict[self.bot.token] = {'image_url': self.store_image.url,
                                              'telegr_file_id': msg.photo[0].file_id}

        self.store_pic_file_json = json.dumps(token_to_file_dict)
        self.save()
        return token_to_file_dict[self.bot.token]['telegr_file_id']

    def __str__(self):
        return self.title



class BotUser(models.Model):
    bot = models.ForeignKey(AcurBot, on_delete=models.DO_NOTHING)

    bot_user_id  = models.CharField(max_length=100)
    main_resp_path = models.CharField(max_length=100)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    username = models.CharField(max_length=100)
    is_operator = models.BooleanField(default=False)

    is_operator_dicussing = models.BooleanField(default=False)

    last_active = models.DateTimeField()
    def upd_last_active(self):
        self.last_active = timezone.now()
        self.save()


    def __str__(self):
        return str(self.id) + ' '+  str(self.bot_user_id)



class StartEvent(models.Model):
    bot_user = models.ForeignKey(BotUser, on_delete=models.CASCADE)
    date_added = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return str(self.bot_user.bot_user_id) + ' ' + str(self.date_added)

class OrgSubscription(models.Model):
    bot_user = models.ForeignKey(BotUser, on_delete=models.CASCADE)
    org = models.ForeignKey(Store, on_delete=models.CASCADE)
    date = models.DateField(auto_now_add=True)

    def __str__(self):
        return self.org.title


class MessageLog(models.Model):
    bot_user = models.ForeignKey(BotUser, on_delete=models.CASCADE)
    text = models.CharField(max_length=500)
    def __str__(self):
        return self.text


class CardShowList(models.Model):
    card_list_json = models.CharField(max_length=800)




class UserToOperatorMsgList(models.Model):
    sent_time = models.DateTimeField(auto_now_add=True)
    text = models.CharField(max_length=4500)
    sender_to_bot_msg_id = models.CharField(max_length=200)
    sender_bot_user = models.ForeignKey(BotUser, on_delete=models.CASCADE, related_name='msg_list_sender_bot_user')


class InterBotMsg(models.Model):
    sent_time = models.DateTimeField(auto_now_add=True)
    text = models.CharField(max_length=4500)

    bot_to_receiver_msg_id = models.CharField(max_length=200)
    sender_to_bot_msg_id = models.CharField(max_length=200)


    sender_bot_user = models.ForeignKey(BotUser, on_delete=models.CASCADE,related_name='inter_bot_sender_bot_user')
    receiver_bot_user = models.ForeignKey(BotUser, on_delete=models.CASCADE,related_name='inter_bot_receiver_bot_user')

    user_to_operator_msg_list = models.ForeignKey(UserToOperatorMsgList, null=True, blank=True, on_delete=models.DO_NOTHING)

    def get_receiver_bot_user_teleg_id(self):
        return self.receiver_bot_user.bot_user_id

    def get_sender_bot_user_teleg_id(self):
        return self.sender_bot_user.bot_user_id

    def get_user_to_operator_msg_list(self):
        return self.user_to_operator_msg_list


