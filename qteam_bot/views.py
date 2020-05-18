from django.shortcuts import render

# Create your views here.
from django.http import HttpResponse
import datetime
from rest_framework import authentication, permissions
from rest_framework import routers, serializers, viewsets

from django.contrib.auth.models import User, Group
from rest_framework import viewsets
from .serializers import UserSerializer, GroupSerializer, BotUserSerializer
from .models import BotUser
from rest_framework.response import Response
from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes
from django.db import transaction
from django.http import Http404
from rest_framework.exceptions import ValidationError
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django.utils import timezone
import json
import requests
from random import shuffle
import time
