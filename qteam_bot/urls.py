from django.urls import path

from . import views
from django.urls import include, path
from rest_framework import routers, serializers, viewsets
from django.conf.urls import url, include

from django.urls import include, path
from rest_framework import routers



# Wire up our API using automatic URL routing.
# Additionally, we include login URLs for the browsable API.
urlpatterns = [

    path('', views.IntentModelApi.as_view(), name='model'),

]


