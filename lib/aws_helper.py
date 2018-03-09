import boto3
import botocore
import json
import base64
import os
from boto3.dynamodb.conditions import Key, Attr
import urllib2

# Contains utility functions that help with AWS-related things
class AwsEnvironmentVars:
    ALEXA_DB_TABLE = 'AlexaDbTable'
    BOI_RESPONSE_TABLE = 'BoiResponseTable'
    ALEXA_KMS_KEY_ID = 'KmsKeyId'

def getS3FileInfo (bucketName, objectKey):
    client = boto3.client('s3', region_name='us-east-1')
    bucketObj = client.get_object(Bucket=bucketName, Key=objectKey)
    return bucketObj

def getS3FileStream (bucketName, objectKey):
    # stream the file into a byte array object
    return getS3FileInfo(bucketName, objectKey)['Body']
    
def getKmsClient ():
    client = boto3.client('kms', region_name='us-east-1')
    return client

def getSqsClient ():
    sqs = boto3.resource('sqs', region_name='us-east-1')
    return sqs

def getKinesisClient ():
    client = boto3.client('kinesis', region_name='us-east-1')
    return client

def getKmsKeyId (keyId=AwsEnvironmentVars.ALEXA_KMS_KEY_ID):    
    #keyId = '29bfb18d-8fe3-473a-affd-3e95d935e1fb'
    #return keyId
    return getEnvVar(keyId)

def encryptUsingKms (clearText):
    client = getKmsClient()
    keyId = getKmsKeyId()
    response = client.encrypt(KeyId=keyId,Plaintext=clearText)
    encryptedData = response['CiphertextBlob']
    encodedData = base64.b64encode(encryptedData)
    return encodedData

def decryptUsingKms (encryptedAndEncoded):
    client = getKmsClient()
    decodedData = base64.b64decode(encryptedAndEncoded)
    return client.decrypt(CiphertextBlob=str(decodedData))['Plaintext']

def putEncryptedOnSqsQueue (queueName, message):
    encrypted = encryptUsingKms(message)
    return putOnSqsQueue (queueName, encrypted)

def putOnSqsQueue (queueName, message):
    sqs = getSqsClient()
    queue = sqs.get_queue_by_name(QueueName=queueName)
    return queue.send_message(MessageBody=message)

def putInKinesis (streamName, message, partitionKey):
    client = getKinesisClient()
    return client.put_record(
        StreamName=streamName,
        Data=message,
        PartitionKey=partitionKey)

def getEnvVar (varName):
    return os.environ[varName]

def findItemsByKey (itemId, keyName, tableName, sortKey = None):  
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    table = dynamodb.Table(tableName)
    
    cleanItemId = urllib2.unquote(itemId)

    print ('querying ' + tableName + ' for : ' + cleanItemId)
    response = table.query(KeyConditionExpression=Key(keyName).eq(cleanItemId))
    foundItems = response['Items']
    
    if sortKey != None:
        print ('sorting...')
        foundItems = sorted(foundItems, key=lambda k: k.get(sortKey,0))

    return foundItems
