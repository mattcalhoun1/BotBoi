import time
import calendar
import json
import base64
import hashlib
import rsa

# Requires python-rsa
# Requires cert directory that contains 
class BoiTokenGenerator:
    def __init__(self, keyFile):
        # initialize the private key 
        self.signingKey = self.__getPrivateKey(keyFile)

    def generateJwtToken(self, userId, extraParamName = None, extraParamValue = None):
        header = {
            'alg': 'http://www.w3.org/2001/04/xmldsig-more#rsa-sha1',
            'typ':'JWT'
        }
        
        payload = {
            'nbf': calendar.timegm(time.gmtime()) - 60,
            'exp': calendar.timegm(time.gmtime()) + 600,
            'iat': calendar.timegm(time.gmtime()),
            'UserName': 'boibot',
            'BoiUserId': userId,
            'iss':'BOI',
            'aud':'BOI'
        }

        if extraParamName != None and len(extraParamName) > 0:
            payload[extraParamName] = extraParamValue
        
        tokenBase = self.__generateTokenBase(header, payload).replace('=', '')
        
        signature = self.generateSignature(tokenBase)
        
        token = tokenBase + '.' + signature
        
        return self.__httpEncodeJwt(token).strip('=')
        
    def __generateTokenBase (self, header, payload):    
        payloadStr = json.dumps(payload, indent=4, separators=(',', ': '))    
        headerStr = json.dumps(header, indent=4, separators=(',', ': '))    
        encodedPayload = base64.b64encode(payloadStr)
        encodedHeader = base64.b64encode(headerStr)
        return encodedHeader + '.' + encodedPayload

    def generateHash (self, textToHash):
        sha1 = hashlib.sha1()
        sha1.update(textToHash)
        digest = sha1.digest()
        
        return digest

    def generateSignature (self, textToSign):
        # Sign the hash
        signature = rsa.sign(textToSign, self.signingKey, 'SHA-1')
        
        # encode the signature
        return base64.b64encode(signature)
        
    def __getPrivateKey (self, fileName):
        if isinstance(fileName, basestring):
            with open(fileName, "rb") as privatefile:
                keydata = privatefile.read()
                privkey = rsa.PrivateKey.load_pkcs1(keydata, format='DER')
            return privkey
        elif fileName != None:
            keydata = fileName.read()
            privkey = rsa.PrivateKey.load_pkcs1(keydata, format='DER')
            return privkey
        else:
            return None
            
        
    def __httpEncodeJwt (self, jwt):
        return jwt.replace('+', '-').replace('/', '_')  
