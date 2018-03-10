# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import os
import time
from dateutil import parser
import datetime
from datetime import timedelta
import locale
import sys
import base64
import boto3
from boto3.dynamodb.conditions import Key, Attr
import json
import urllib2
import lib.aws_helper as aws_helper
import lib.lex_helper as lex_helper
import lib.jwt_helper as jwt_helper
import dateutil
import pytz
from dateutil import parser
from random import randint
from bot_action import BotAction, LexAction, PinPromptAction, DidntUnderstandAction
import uuid

class BoiBotEnvVars:
    ALEXA_USER_TABLE = 'BoiUserTable'
    ALEXA_USER_ID_COLUMN = 'BoiUserIdColumn'
    ALEXA_USER_ID_INDEX = 'BoiUserIdIndex'

'''
    This is the base class for interfaces that allow users
    to interact with the BOI / Lex bot framework. 
    To utilize this, override the various methods that
    contain request/response format, security details, etc.
'''
class BoiBotInterface:
    def getBotResponse(self, event):
        print ('bot inteface did not override getBotResponse')
        pass

    def getJwtAccessToken (self, event):
        print ('bot did not override getJwtAccessToken')
        pass

    def validateRequest (self, request, event):
        print ('bot interface did not override request validation')
        pass

    def build_speechlet_response (self, title, output, reprompt_text, should_end_session, cardType, session_attributes):
        print ('bot interface did not override build_speechlet_response')
        pass

    def build_response(self, session_attributes, speechlet_response):
        print ('bot interface did not override build_response')
        pass

    def getLinkMessage(self):
        print ('bot interface did not override getLinkMessage')
        pass

    def getGeneralError (self):
        speech_output = 'I am not able to help you at the moment, please try again later.'
        reprompt_text = speech_output
        return self.build_response({}, self.build_speechlet_response(
            'Unavailable', speech_output, reprompt_text, True))

    def getDidntUnderstand (self, intent, session):
        print ('did not understand')
        session_attributes = self.getSessionAttributes(session)
        nextAction = DidntUnderstandAction(self.getJwtAccessToken(session), session_attributes)
        botResponse = nextAction.getFulfilledResponse()
        return self.build_response(session_attributes, self.build_speechlet_response(
            botResponse.getCardTitle(), 
            botResponse.getResponseText(), 
            botResponse.getResponseText(), 
            botResponse.isSessionEnded(), 
            'Standard', 
            session_attributes))

    def getLinkResponse (self, intent, session):
        return self.build_response(self.getSessionAttributes(session), self.build_speechlet_response(
            'Link an Account', self.getLinkMessage(), None, True, 'LinkAccount'
        ))

    def getUtteredPhrase (intent):
        print ('bot interface did not override getUtteredPhrase')
        pass

    def askLex (self, intent, session, isAnonymous = False):
        print (str(intent))
        session_attributes = self.getSessionAttributes(session)
        userQuestion = self.getUtteredPhrase(intent)

        #if 'LexSession' in session['attributes'] and session['attributes']['LexSession'] == True:
        #    # stuff the user's input into encrypted area for later, send the id to lex 
        #    userQuestion = str(randint(1,10000))
        if userQuestion == None:
            return self.getDidntUnderstand(intent, session)

        print ('Asking/Telling Lex: ' + userQuestion)
        lexAction = LexAction(None if isAnonymous else self.getJwtAccessToken(session), 
            session_attributes, 
            userQuestion)
        botResponse = lexAction.getFulfilledResponse()
        return self.build_response(session_attributes, self.build_speechlet_response(
            botResponse.getCardTitle(), 
            botResponse.getResponseText(), 
            botResponse.getResponseText(), 
            botResponse.isSessionEnded(), 
            'Standard', 
            session_attributes))

    def getPinPrompt (self, intent, session):
        print ('prompting for pin')
        session_attributes = self.getSessionAttributes(session)
        pinPromptAction = PinPromptAction(self.getJwtAccessToken(session), session_attributes)
        botResponse = pinPromptAction.getFulfilledResponse()
        return self.build_response(session_attributes, self.build_speechlet_response(
            botResponse.getCardTitle(), 
            botResponse.getResponseText(), 
            botResponse.getResponseText(), 
            botResponse.isSessionEnded(), 
            'Standard', 
            session_attributes))

    def findUserById (self, id):
        # save to dynamodb    
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        table = dynamodb.Table(aws_helper.getEnvVar(BoiBotEnvVars.ALEXA_USER_TABLE))
        print ('querying for user: ' + id)
        id = urllib2.unquote(str(id))

        user = None
        if len(aws_helper.getEnvVar(BoiBotEnvVars.ALEXA_USER_ID_INDEX)) > 0:
            response = table.query(
                IndexName=aws_helper.getEnvVar(BoiBotEnvVars.ALEXA_USER_ID_INDEX),
                KeyConditionExpression=Key(aws_helper.getEnvVar(BoiBotEnvVars.ALEXA_USER_ID_COLUMN)).eq(id)
            )
        
            print ('found ' + str(response))    
            if 'Items' in response.keys() and len(response['Items']) > 0:
                user = response['Items'][0]
        else:
            response = table.get_item(Key={aws_helper.getEnvVar(BoiBotEnvVars.ALEXA_USER_ID_COLUMN):id})
            print ('found ' + str(response))    
            user = response['Item']
        
        self.decryptFields(user)
        return user

    def getDefaultRepromptText (self):
        return 'I can help you with various things. How can I help?'

    def getNextIntentPrompt (self):
        return 'How else can I help you today?'

    def isPinRequired (self, user):
        # return true if this user requires a pin
        #print ('user pin = ' + str(user['pin']))
        return 'pin' in user.keys() and len(user['pin']) > 0

    def decryptFields(self, user):
        print('Decrypting user...')
        if 'pin' in user.keys():
            user['pin'] = aws_helper.decryptUsingKms(user['pin'])

    def getAppUrlPrefix (self):
        return aws_helper.getEnvVar('AppUrlPrefix')

    def extract_user_id_from_jwt (self, jwt):
        return jwt_helper.extract_from_payload('BoiUserId', jwt)

    def getSessionAttributes (self, session):
        print ('bot interface did not override getSessionAttributes')
        pass
