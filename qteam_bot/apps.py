from django.apps import AppConfig


class QteamBotConfig(AppConfig):
    name = 'qteam_bot'


    def ready(self):
        # Singleton utility
        # We load them here to avoid multiple instantiation across other
        # modules, that would take too much time.
        print("Loading intent_model..."),
        import json
        import copy
        from deeppavlov import train_model, configs, build_model
        import pickle
        config_path = 'acur_intent_config.json'
        my_config = json.load(open(config_path))
        tmp_config = copy.deepcopy(my_config)
        tmp_config['chainer']['out'] = ['y_pred_labels', 'y_pred_probas']
        tmp_config['chainer']['pipe'][-2]['out'] = ['y_pred_ids', 'y_pred_probas']


        global intent_model
        intent_model = build_model(tmp_config)
        print('модель загрузили кое-как')
        print("ok!")