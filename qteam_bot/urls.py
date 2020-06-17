from . import views
from django.urls import include, path


urlpatterns = [

    path('', views.SendMessageApi.as_view(), name='messaging'),
    path('msg_to_operator/', views.MessageToOperatorApi.as_view(), name='msg_to_operator'),

]