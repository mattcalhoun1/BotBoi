from __future__ import print_function

import json
from boi_rest_bot_interface import BoiRestBotInterface

def respond(err, res=None):
    return {
        'statusCode': '400' if err else '200',
        'body': err.message if err else str(res),
        'headers': {
            'Content-Type': 'application/json',
        },
    }
    
def lambda_handler(event, context):
    print("Received event: " + json.dumps(event, indent=2))

    # get state / code params on redirect_url, if login succeeds
    postedBody = json.loads(event['body'])
    
    botInterface = BoiRestBotInterface ()
    response = botInterface.getGeneralError()
    
    # Check security on the request
    if botInterface.validateRequest(postedBody, postedBody):
        response = json.dumps(botInterface.getBotResponse(postedBody))

    return respond(None,response)
