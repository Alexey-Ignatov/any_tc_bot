from . import views
from django.urls import include, path


urlpatterns = [

    path('', views.SendMessageApi.as_view(), name='messaging'),

]