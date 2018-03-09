# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os
import time
from dateutil import parser
import datetime
from datetime import timedelta
import sys
import base64
import json
import lib.aws_helper as aws_helper
import lib.aws_sig_checker as aws_sig_checker
import dateutil
import pytz
from random import randint
from boi_bot_interface import BoiBotInterface
import uuid

''' 
    This class contains Google-specific details for interacting
    with the BOI / Lex bot framework.
'''
class BoiGoogleBotInterface(BoiBotInterface):
    def validateRequest (self, request, event):
        # Make sure the request is not old (per Amazon standard)
        if aws_helper.getEnvVar('TestMode') == 'true' or self.check_request_freshness(event):
            # Check that the request was signed properly
            if aws_helper.getEnvVar('TestMode') == 'true' or aws_sig_checker.checkSignature(request):
                return True
            else:
                print ('Signature is NOT valid!')
        else:
            print ('warning, request is old!!')
        return False

    def getJwtAccessToken(self, session):
        # to do:
        # if test mode, return dummy jwt token
        
        if session != None and 'user' in session.keys() and 'accessToken' in session['user'].keys():
            return session['user']['accessToken']
        return None

    def getUtteredPhrase (self, intent):
        # return most recent uttered phrase
        utteredPhrase = intent['input']['rawInputs'][len(intent['input']['rawInputs']) - 1]
        return utteredPhrase

    def findUserBySession(self, session):
        if 'attributes' in session.keys() and 'boiUser' in session['attributes'].keys():
            return session['attributes']['boiUser']

        if 'user' in session.keys() and 'accessToken' in session['user'].keys():
            jwtToken = session['user']['accessToken']
            userId = self.extract_user_id_from_jwt(jwtToken)
            user = self.findUserById(userId)
            if user != None:
                session['attributes'] = {'boiUser':user}
                print ('found user: ' + str(user))

            return user

        return None

    def check_request_freshness (self, event):
        # request can be up to 90 seconds old
        isFresh = False
        try:
            requestTimeStr = event['request']['timestamp']
            requestTime = parser.parse(requestTimeStr)

            now = datetime.datetime.now(tz=pytz.utc)

            requestAge = (now - requestTime).total_seconds()
            isFresh = requestAge <= 90
        except:
            print ('unable to check event timestamp!')
        return isFresh

    def build_speechlet_response(self, title, output, reprompt_text, should_end_session, cardType = 'Simple', session_attributes = None):
        speech = output
        if should_end_session == False and (('?' in output) == False and ('PIN' in title) == False and ('Welcome' in title) == False):
            # append the next intent prompt 
            speech = speech + ' ' + self.getNextIntentPrompt()

        if reprompt_text == None:
            reprompt_text = self.getDefaultRepromptText()

        if cardType == 'Standard':
            adNum = str(randint(1,3))
            return {
                'outputSpeech': {
                    'type': 'PlainText',
                    'text': speech
                },
                'card': {
                    'type': cardType,
                    'title': title,
                    'text': output,
                    'image': {
                        'smallImageUrl': str(self.getAppUrlPrefix() + '/logo_small.png'),
                        'largeImageUrl': str(self.getAppUrlPrefix() + '/logo_large.png')
                    }
                },
                'reprompt': {
                    'outputSpeech': {
                        'type': 'PlainText',
                        'text': reprompt_text
                    }
                },
                'shouldEndSession': should_end_session
            }
        else:
            return {
                'outputSpeech': {
                    'type': 'PlainText',
                    'text': speech
                },
                'card': {
                    'type': cardType,
                    'title': title,
                    'content': output
                },
                'reprompt': {
                    'outputSpeech': {
                        'type': 'PlainText',
                        'text': reprompt_text
                    }
                },
                'shouldEndSession': should_end_session
            }


    def build_response(self, session_attributes, speechlet_response):
        return {
            'conversationToken': session_attributes['conversation']['conversationId'],
            'expectedUserResponse': speechlet_response['shouldEndSession'],
            'expectedInputs':[],
            'finalResponse':speechlet_response['outputSpeech']['text'],
            'isInSandbox':False
        }

    def getLinkMessage(self):
        return 'It looks like you need to link an account with Google. Please open the Google Home app and link an account.'

    def getSessionAttributes (self, session):
        sessionAttributes = {}
        if 'attributes' in session.keys():
            sessionAttributes = session['attributes']

        if ('sessionId' in sessionAttributes.keys()) == False:
            sessionAttributes['sessionId'] = session['conversation']['conversationId']
            #sessionAttributes['sessionId'] = uuid.uuid4().hex

        return sessionAttributes

    def getBotResponse(self, event):
        print ('received google request')
        print(str(event))

        return self.askLex(event, event)


