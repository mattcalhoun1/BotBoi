import boto3
import botocore
import json
import base64
import os

def postToLex (botName, botAlias, userId, message, sessionAttributes = None, requestAttributes = None):
    client = boto3.client('lex-runtime', region_name='us-east-1')
    #response = client.post_content (
    #    botName = botName,
    #    botAlias = botAlias,
    #    userId = userId,
    #    sessionAttributes = {} if sessionAttributes == None else sessionAttributes,
    #    requestAttributes = {} if requestAttributes == None else requestAttributes,
    #    contentType = 'text/plain; charset=utf-8',
    #    accept = 'text/plain; charset=utf-8',
    #    inputStream=message    
    #)

    response = client.post_text (
        botName = botName,
        botAlias = botAlias,
        userId = userId,
        sessionAttributes = {} if sessionAttributes == None else sessionAttributes,
        requestAttributes = {} if requestAttributes == None else requestAttributes,
        inputText=message
    )
    return response

def nextLexPrompt (lexResponse):
    return lexResponse['message']

def isIntentReadyToBeFulfilled (lexResponse):
    return 'dialogState' in lexResponse.keys() and lexResponse['dialogState'] == 'ReadyForFulfillment'

def isLexDone (lexResponse):
    return 'dialogState' in lexResponse.keys() and (lexResponse['dialogState'] == 'ReadyForFulfillment' or lexResponse['dialogState'] == 'Failed')

def getIntent (lexResponse):
    return lexResponse['intentName']

def getUserInput (lexResponse):
    if lexResponse != None and 'slots' in lexResponse.keys():
        return lexResponse['slots']
    return {}

def didLexUnderstand (lexResponse):
    return 'dialogState' in lexResponse.keys() and lexResponse['dialogState'] != 'ElicitIntent'