import os
import time
from dateutil import parser
import datetime
from datetime import timedelta
import locale
import sys
import json
import dateutil
import pytz
from dateutil import parser
from random import randint
from string import Formatter
from collections import OrderedDict
import lib.lex_helper as lex_helper
import lib.aws_helper as aws_helper

class BotActionEnvVars:
    BOI_RESPONSE_TABLE = 'BoiResponseTable'
    LEX_BOT_NAME = 'LexBotName'
    LEX_BOT_ALIAS = 'LexBotAlias'

class BotAction:
    def __init__(self, jwt, userSession, fulfillmentData):
        self.jwt = jwt
        self.userSession = userSession
        self.fulfillmentData = fulfillmentData

    def getFulfilledResponse (self):
        self.setupLocale()
        speech_output = None

        serviceResponses = {}

        # Fire any rules to figure out which response..if > 1
        responseTemplate = self.getFulfilledResponseTemplate(serviceResponses)

        # Pre-load any service calls that will be required to fulfill a response
        apiResponses = self.getServiceResponsesForTemplate(responseTemplate, serviceResponses)
        #print (str(apiResponses))

        # Replace pieces of the text with data from the responses
        textResponse = ''
        for ele in Formatter().parse(responseTemplate):
            if len(ele) > 0 and ele[0] != None:
                textResponse = textResponse + ele[0]

                if len(ele) > 1 and ele[1] != None:
                    textResponse = textResponse + str(self.getFormattedFieldValue (ele[1], apiResponses))


        return BotResponse(textResponse, self.getCardTitle(), self.shouldSessionEnd(apiResponses))

    def getFormattedFieldValue (self, fullFieldName, serviceResponses):
        # Maybe computed or complex or simple. If it's computed,
        # the implementation is expected to be in a subclass.
        # if it's simple, it's expected to be a top level attribute of a 
        # rest response
        svcName = fullFieldName.split('.')[0]
        if svcName.startswith('@'):
            # Invoke the method on self (useful for subclasses)
            # If there's a '.' after the method name, retrieve the given field (and format)
            methodParts = fullFieldName.split('.')
            methodName = 'get' + methodParts[0][1:]
            methodParams = [serviceResponses]
            result = getattr(self, methodName)(*methodParams)
            if len(methodParts) > 1:
                attrName = methodParts[1]
                fieldValue = result[attrName]
                return self.formatFieldValue(attrName, fieldValue)
            else:
                return result
        else:
            fieldName = fullFieldName.split('.')[1]
            if fieldName in serviceResponses[svcName].keys():
                fieldValue = serviceResponses[svcName][fieldName]
                return self.formatFieldValue(fieldName, fieldValue)
            else:
                return 'field not found'

    def formatFieldValue (self, fieldName, fieldValue):
        try:
            if fieldName.endswith('Date'):
                niceFormat = '%B %d'
                fieldDate = parser.parse(fieldValue)
                return fieldDate.strftime(niceFormat)
            elif fieldName.endswith('Balance') or fieldName.endswith('Amount'):
                return locale.currency(fieldValue)
        except:
            print ('field format threw exception')
        
        return fieldValue

    def getServiceResponsesForTemplate (self, messageTemplate, serviceResponses):
        # read the template, see which fields are required
        for ele in Formatter().parse(messageTemplate):
            if len(ele) > 1 and ele[1] != None:
                svcName = ele[1].split('.')[0]
                if svcName.startswith('@') == False:
                    self.populateServiceResponse(svcName, serviceResponses)
        
        return serviceResponses
    
    def populateServiceResponse (self, serviceName, serviceResponses):
        if (serviceName in serviceResponses.keys()) == False:
            print ('Invoking api method: get' + serviceName)
            serviceResponses[serviceName] = self.invokeApiMethod(serviceName)
            

    # Invokes appropriate rest call on external api...for instance,
    # if methodName = Customer, it will invoke GET [api url]/Customer
    def invokeApiMethod (self, methodName, methodParams = [0]):
        if self.jwt == None:
            raise Exception('Authentication required')

        # if api is an actual class, not a rest api
        #return getattr(self.api, 'get' + methodName)(*methodParams)
        print ('Not yet implemented')


    def getAllResponseTemplates (self):
        intentName = self.fulfillmentData['intent']
        boiResponses = aws_helper.findItemsByKey(intentName, 'intent', aws_helper.getEnvVar(BotActionEnvVars.BOI_RESPONSE_TABLE), 'priority')
        matchingResponses = OrderedDict()
        for resp in boiResponses:
            matchingResponses[(resp.get('rule','default'))] = resp.get('response','No response key.')
        return matchingResponses

    def getFulfilledResponseTemplate (self, serviceResponses):
        # loop through each potential response, firing the rules
        # until we find one that matches, or until we hit the default
        potentialResponses = self.getAllResponseTemplates()
        conditionMethods = potentialResponses.keys()
        conditionParams = [serviceResponses] # responses will/may be built up as conditions are checked

        for conditionMethod in conditionMethods:
            # If we've reached the default, return that
            if conditionMethod == 'default' or conditionMethod == '':
                return potentialResponses[conditionMethod]
            else:
                # Invoke the condition (method)
                if getattr(self, conditionMethod)(*conditionParams):
                    return potentialResponses[conditionMethod]
        
        print ('unable to find suitable condition or response template!')
        return 'Sorry, I was not able to help with that.'

    def getCardTitle (self):
        return 'Default Card Title'

    def shouldSessionEnd (self, serviceResponses):
        return False

    def setupLocale (self):
        try:
            locale.setlocale(locale.LC_ALL, 'en_US')
        except:
            # must be windows
            try:
                locale.setlocale( locale.LC_ALL, 'English_United States.1252' )
            except:
                print ('warning: unable to set locale to en_US, default will be used')        

    def isAuthorizationRequired ():
        return True

class LexAction (BotAction):
    def __init__ (self, jwt, userSession, userText):
        BotAction.__init__(self, jwt, userSession, {})
        self.userText = userText
        self.lexResponse = None
        self.cardTitle = 'Boi Assistant'

    def getCardTitle (self):
        return self.cardTitle

    def shouldSessionEnd (self, serviceResponses):
        return self.__getActionForLexResponse (self.__getLexResponse (serviceResponses)).shouldSessionEnd(serviceResponses)
    
    def getAllResponseTemplates(self):
        return OrderedDict([
            ('isLexDone', '{@FinalResponse}'),
            ('default', '{@NextPrompt}')
            ])

    def __getLexResponse (self, serviceResponses):
        if self.lexResponse == None:
            # speak to lex 
            user = 'py.' + str(self.userSession.get('sessionId', '0'))
            user = (user + '.anonymous') if self.jwt == None else user
            print ('speaking to lex as user: ' + user)
            self.lexResponse = lex_helper.postToLex(
                aws_helper.getEnvVar(BotActionEnvVars.LEX_BOT_NAME), 
                aws_helper.getEnvVar(BotActionEnvVars.LEX_BOT_ALIAS), 
                user, 
                self.userText, 
                self.__getLexSession(serviceResponses))

            # Check whether the selected action requires authentication
            if self.jwt == None and self.__getActionForLexResponse(self.lexResponse).isAuthorizationRequired():
                print ('Intent ' + lex_helper.getIntent(self.lexResponse) + ' requires authorization.')
                raise Exception('Authorization required')

        return self.lexResponse

    def __getActionForLexResponse (self, lexResponse):
        lexIntentName = 'DidntUnderstand'
        if lex_helper.didLexUnderstand(lexResponse):
            lexIntentName = lex_helper.getIntent(lexResponse)

        botClass = getattr(sys.modules[__name__], 'DefaultAction')
        try:
            botClass = getattr(sys.modules[__name__], lexIntentName + 'Action')
            print ('Found action class ' + lexIntentName)
        except:
            # Just use default action to fulfill
            print ('No action class found for ' + lexIntentName + '. Using DefaultAction.')
            pass
        fulfillmentData = lex_helper.getUserInput(lexResponse)
        fulfillmentData['intent'] = lexIntentName
        nextAction = botClass(self.jwt, self.userSession, fulfillmentData)
        return nextAction

    def isLexDone (self, serviceResponses):
        return lex_helper.isLexDone(self.__getLexResponse(serviceResponses)) or lex_helper.didLexUnderstand(self.__getLexResponse(serviceResponses)) == False

    def getFinalResponse (self, serviceResponses):
        if lex_helper.isIntentReadyToBeFulfilled(self.__getLexResponse(serviceResponses)) or lex_helper.didLexUnderstand(self.__getLexResponse(serviceResponses)) == False:
            print ('Lex returned: ' + str(lex_helper.getUserInput(self.__getLexResponse(serviceResponses))))
            nextAction = self.__getActionForLexResponse (self.__getLexResponse(serviceResponses))
            subResponse = nextAction.getFulfilledResponse()
            self.cardTitle = subResponse.getCardTitle()
            self.endSession = subResponse.isSessionEnded()
            return subResponse.getResponseText()
        else:
            return lex_helper.nextLexPrompt(self.__getLexResponse(serviceResponses))

    def getNextPrompt(self, serviceResponses):
        return lex_helper.nextLexPrompt(self.__getLexResponse(serviceResponses))

    # Populates the lex session with required attributes.
    def __getLexSession (self, serviceResponses):
        # If this is an anonymous request, don't try prefilling
        # the Lex session with data specific to the user
        if self.jwt == None:
            return {}

        # to do, add better session capabilities. for now,
        # just return cached service responses
        return serviceResponses

class DefaultAction (BotAction):
    def __init__(self, jwt, userSession, fulfillmentData):
        BotAction.__init__(self, jwt, userSession, fulfillmentData)

    def getAllResponseTemplates (self):
        intentName = self.fulfillmentData['intent']
        apiResponses = aws_helper.findItemsByKey(intentName, 'intent', aws_helper.getEnvVar(BotActionEnvVars.BOI_RESPONSE_TABLE), 'priority')
        matchingResponses = OrderedDict()
        for resp in apiResponses:
            matchingResponses[(resp.get('rule','default'))] = resp.get('response','No response key.')

        return matchingResponses

    def getCardTitle (self):
        return 'Boi Assistant'

    def isAuthorizationRequired (self):
        # responses from default action are allowed to be returned
        # without user logging in..provided no user-specific info
        # is present
        # If a response includes any placeholders (ex: {Customer.FirstName})
        # then authorization will be required (exception will be thrown)
        return False

class GoodbyeAction (BotAction):
    def __init__(self, jwt, userSession, fulfillmentData):
        BotAction.__init__(self, jwt, userSession, fulfillmentData)

    def shouldSessionEnd (self, serviceResponses):
        return True    
    
    def isAuthorizationRequired (self):
        return False

    def getCardTitle (self):
        return 'Boi Assistant'

class DidntUnderstandAction (BotAction):
    def __init__(self, jwt, userSession, fulfillmentData = None):
        BotAction.__init__(self, jwt, userSession, {'intent':'DidntUnderstand'})

    def isAuthorizationRequired (self):
        return False

    def getCardTitle (self):
        return 'Boi Assistant'

class PinPromptAction (BotAction):
    def __init__(self, jwt, userSession):
        BotAction.__init__(self, jwt, userSession, {'intent':'PinPrompt'})

    def isTooManyAttempts (self, serviceResponses):
        return 'pinAttempts' in self.userSession.keys() and self.userSession['pinAttempts'] > 2

    def isIncorrectPin (self, serviceResponses):
        return 'pinAttempts' in self.userSession.keys() and self.userSession['pinAttempts'] > 0

    def getCardTitle (self):
        return 'Provide Your PIN'

    def isAuthorizationRequired (self):
        return False

    def isAuthorizationRequired (self):
        return False

    def shouldSessionEnd (self, serviceResponses):
        return self.isTooManyAttempts(serviceResponses)
        

class BotResponse ():
    def __init__(self, responseText, cardTitle, endSession = False):
        self.responseText = responseText
        self.cardTitle = cardTitle
        self.endSession = endSession
    
    def getResponseText (self):
        return self.responseText

    def getCardTitle (self):
        return self.cardTitle

    def isSessionEnded (self):
        return self.endSession