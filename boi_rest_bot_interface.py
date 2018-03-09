# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import json
from random import randint
from boi_bot_interface import BoiBotInterface
import uuid

''' 
    This class contains a simple rest API for interfacing
    with the BOI / Lex bot framework.
'''
class BoiRestBotInterface(BoiBotInterface):
    def validateRequest (self, request, event):
        return True

    def getJwtAccessToken(self, session):
        if session != None and 'accessToken' in session.keys():
            return session['accessToken']
        return None

    def getUtteredPhrase (self, intent):
        return intent['userText']

    def build_speechlet_response(self, title, output, reprompt_text, should_end_session, cardType = 'Simple', session_attributes = None):
        speech = output
        if should_end_session == False and (('?' in output) == False and ('Welcome' in title) == False):
            # append the next intent prompt 
            speech = speech + ' ' + self.getNextIntentPrompt()
        return {
            'title': title,
            'text': speech,
            'shouldEndSession': should_end_session
        }

    def build_response(self, session_attributes, speechlet_response):
        return {
            'version': '1.0',
            'sessionAttributes': session_attributes,
            'response': speechlet_response
        }

    def getSessionAttributes (self, session):
        sessionAttributes = {}
        if 'attributes' in session.keys():
            sessionAttributes = session['attributes']

        if ('sessionId' in sessionAttributes.keys()) == False:
            sessionAttributes['sessionId'] = uuid.uuid4().hex

        return sessionAttributes

    def getBotResponse(self, event):
        print ('received rest post: ' + str(event))
        return self.askLex(event['request'], event['session']) 
