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
    This class contains Alexa-specific details for interacting
    with the BOI / Lex bot framework.
'''
class BoiAlexaBotInterface(BoiBotInterface):
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
        if session != None and 'user' in session.keys() and 'accessToken' in session['user'].keys():
            return session['user']['accessToken']
        return None

    def getUtteredPhrase (self, intent):
        mappedPhrases = {
            'AMAZON.YesIntent':'yes',
            'AMAZON.NoIntent':'no',
            'AMAZON.CancelIntent':'good bye',
            'AMAZON.StopIntent':'good bye',
            'AMAZON.HelpIntent':'help'
        }
        if intent['name'] in mappedPhrases.keys():
            utteredPhrase = mappedPhrases[intent['name']]
        elif intent['name'] == 'PIN':
            # User uttered a number , but pin was already spoken (if applicable)
            # so alexa misidentifies as a PIN.
            utteredPhrase = intent['slots']['PinDigits']['value']         
        else:
            if 'CatchAll' in intent['slots'].keys() and 'value' in intent['slots']['CatchAll']:
                utteredPhrase = str(intent['slots']['CatchAll']['value'])

            if 'CatchAllDate' in intent['slots'].keys() and 'value' in intent['slots']['CatchAllDate']:
                utteredPhrase = intent['slots']['CatchAllDate']['value']
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
            'version': '1.0',
            'sessionAttributes': session_attributes,
            'response': speechlet_response
        }

    def getLinkMessage(self):
        return 'It looks like you need to link an account with Alexa. Please open the Alexa app and link an account.'

    def getSessionAttributes (self, session):
        sessionAttributes = {}
        if 'attributes' in session.keys():
            sessionAttributes = session['attributes']

        if ('sessionId' in sessionAttributes.keys()) == False:
            sessionAttributes['sessionId'] = uuid.uuid4().hex

        return sessionAttributes

    def on_session_started(self, session_started_request, session):
        # Called if new Alexa session starts
        print("on_session_started requestId=" + session_started_request['requestId']
            + ", sessionId=" + session['sessionId'])

    def on_launch(self, launch_request, session):
        # Called when the user launches the skill without specifying what they
        # want

        print("on_launch requestId=" + launch_request['requestId'] +
            ", sessionId=" + session['sessionId'])

        user = None
        try:
            user = self.findUserBySession(session)
        except:
            print ('error finding user by session')
        if user == None:
            return self.getLinkResponse(None, session)

        # Check whether PIN applies to this user or not
        if self.isPinRequired(user):
            print ("pin is required now, new session")
            if False == ('attributes' in session.keys()) or False == ('originalIntent' in session['attributes'].keys()):
                # Save the user's original intent info for later
                slots = {}
                originalIntent = {'intent':{'name':'AMAZON.HelpIntent'}, 'slots':slots}
                session['attributes']['originalIntent'] = originalIntent
                session['attributes']['pinAttempts'] = 0
            
            return self.getPinPrompt(None, session)

        return self.askLex(launch_request, session)

    def on_intent(self, intent_request, session, full_request = None):
        # Called when the user specifies an intent for this skill
        
        print("on_intent requestId=" + intent_request['requestId'] +
            ", sessionId=" + session['sessionId'])
            
        intent = intent_request['intent']
        intent_name = intent_request['intent']['name']

        user = None
        try:
            user = self.findUserBySession(session)
        except:
            print ('error finding user by session')

        if user == None:
            return self.getLinkResponse(intent, session)

        public_intents = {'AMAZON.StopIntent', 'AMAZON.CancelIntent'}

        # Check whether PIN applies to this user or not
        print ('on_intent: intent name == ' + intent_name)
        if False == (intent_name in public_intents) and True == self.isPinRequired(user):
            if intent_name == 'PIN' and (False == ('attributes' in session.keys()) or (False == ('PinProvided' in session['attributes'].keys()))):
                # Check the pin
                if intent['slots']['PinDigits']['value'] == user['pin']:
                    # correct pin
                    session['attributes']['PinProvided'] = True
                    # get back the original intent
                    intent = session['attributes']['originalIntent']['intent']
                    intent_name = intent['name']
                    intent['slots'] = session['attributes']['originalIntent']['slots']
                else:
                    # reprompt for pin
                    session['attributes']['pinAttempts'] = session['attributes']['pinAttempts']+1
                    return self.getPinPrompt(intent, session)
            elif False == ('attributes' in session.keys()) or (False == ('PinProvided' in session['attributes'].keys())):
                # If the intent is AskLex, first attempt to request anonymously
                if intent_name == 'AskLex':
                    try:
                        anonymousResponse = self.askLex(intent, session, True)
                        if anonymousResponse != None:
                            return anonymousResponse
                    except:
                        # Guess pin is required. Go ahead and prompt
                        pass
                
                
                print ("pin is required now")
                if False == ('attributes' in session.keys()) or False == ('originalIntent' in session['attributes'].keys()):
                    # Save the user's original intent info for later
                    slots = {}
                    if 'slots' in intent.keys():
                        slots = intent['slots']
                    originalIntent = {'intent':intent, 'slots':slots}
                    session['attributes']['originalIntent'] = originalIntent
                    session['attributes']['pinAttempts'] = 0
                
                return self.getPinPrompt(intent, session)
       
        return self.askLex(intent, session) 

    def on_session_ended(self, session_ended_request, session):
        """ Called when the user ends the session.

        Is not called when the skill returns should_end_session=true
        """
        print("on_session_ended requestId=" + session_ended_request['requestId'] +
            ", sessionId=" + session['sessionId'])
        # add cleanup logic here

    def getBotResponse(self, event):

        print("event.session.application.applicationId=" +
            event['session']['application']['applicationId'])

        #print ('Event: ' + str(event))

        """ 
        Uncomment this if statement and populate with your skill's application ID to
        prevent someone else from configuring a skill that sends requests to this
        function.
        """
        # if (event['session']['application']['applicationId'] !=
        #         "amzn1.echo-sdk-ams.app.[unique-value-here]"):
        #     raise ValueError("Invalid Application ID")

        if event['session']['new']:
            self.on_session_started({'requestId': event['request']['requestId']},
                            event['session'])

        if event['request']['type'] == "LaunchRequest":
            return self.on_launch(event['request'], event['session'])
        elif event['request']['type'] == "IntentRequest":
            return self.on_intent(event['request'], event['session'], event)
        elif event['request']['type'] == "SessionEndedRequest":
            return self.on_session_ended(event['request'], event['session'])

