# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from django.http import JsonResponse
import json
from boi_alexa_bot_interface import BoiAlexaBotInterface
from boi_rest_bot_interface import BoiRestBotInterface
from boi_google_bot_interface import BoiGoogleBotInterface

# Example django implementation, convert to lambda

@csrf_exempt
def index(request):
    # This is the entry point for the BOI request
    event = json.loads(request.body)
    botInterface = None
    
    if 'HTTP_BOICLIENT' in request.META.keys():
        botInterface = BoiRestBotInterface ()
    elif 'surface' in event.keys():
        botInterface = BoiGoogleBotInterface ()
    else:
        botInterface = BoiAlexaBotInterface ()

    response = botInterface.getGeneralError()
    
    # Check security on the request
    if botInterface.validateRequest(request, event):
        response = botInterface.getBotResponse(event)

    return JsonResponse(response)

