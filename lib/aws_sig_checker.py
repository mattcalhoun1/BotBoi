import requests
import rsa
import hashlib
import Crypto
import Crypto.Signature
from Crypto.Signature import PKCS1_v1_5 as pkcs1_15
import inspect
from Crypto.Util.asn1 import DerSequence
from Crypto.PublicKey import RSA
import Crypto.Hash
from Crypto.Hash import SHA
from binascii import a2b_base64
import base64
import pyasn1
from pyasn1_modules import pem, rfc2459
from pyasn1.codec.der import decoder
import StringIO
from dateutil import parser
from datetime import datetime
import pytz
import os

# Amazon requires hosted alexa skills (non-lambdas) to verify
# signature headers on each request.
# See: https://developer.amazon.com/public/solutions/alexa/alexa-skills-kit/docs/developing-an-alexa-skill-as-a-web-service

def extractPems(pem):
    # pem may be multiple certs, so we remove the
    # 'begin cert' and 'end cert' comments, and then 
    # group the cert lines together, one big line for each cert
    lines = pem.replace(" ",'').split()
    encodedCerts = []
    for line in lines:
        if '-' in line:
            # Skip this. Append a new blank cert line
            encodedCerts.append('')
        else:
            encodedCerts[len(encodedCerts)-1] = encodedCerts[len(encodedCerts)-1] + line + '\n'

    # remove all blank cert strings
    certs = []
    for encodedCert in encodedCerts:
        if len(encodedCert) > 0:
            encodedCert = '-----BEGIN CERTIFICATE-----\n' + encodedCert + '-----END CERTIFICATE-----\n'
            certs.append(encodedCert) 
    return certs

def extractCerts (pem):

    # pem may be multiple certs, so we remove the
    # 'begin cert' and 'end cert' comments, and then 
    # group the cert lines together, one big line for each cert
    lines = pem.replace(" ",'').split()
    encodedCerts = []
    for line in lines:
        if '-' in line:
            # Skip this. Append a new blank cert line
            encodedCerts.append('')
        else:
            encodedCerts[len(encodedCerts)-1] = encodedCerts[len(encodedCerts)-1] + line

    # remove all blank cert strings
    certs = []
    for encodedCert in encodedCerts:
        if len(encodedCert) > 0:
            der = a2b_base64(encodedCert)
            cert = DerSequence()
            cert.decode(der)   
            certs.append(cert) 
    return certs

def extractPublicKey(cert):
    tbsCertificate = DerSequence()
    tbsCertificate.decode(cert[0])
    subjectPublicKeyInfo = tbsCertificate[6]
    # Initialize RSA key
    rsa_key = RSA.importKey(subjectPublicKeyInfo)   
    return rsa_key 

def generateHash (textToHash):
    return SHA.new(textToHash)

def validateCertUrl (certUrl):
    # Make sure the cert url is valid, according to Amazon's standards
    if certUrl == None or len(certUrl) == 0:
        return False
    
    if certUrl.startswith('https://s3.amazonaws.com/echo.api/'):
        return True
    elif certUrl.startswith('https://s3.amazonaws.com:443/echo.api/'):
        return True
    
    return False

def validateCertChain (certPem):
    # Ensure this is a good cert
    certs = extractPems(certPem)
    valid = False

    for indvCertPem in certs:
        wrappedPem = StringIO.StringIO(indvCertPem)

        substrate = pem.readPemFromFile(wrappedPem)
        cert = decoder.decode(substrate, asn1Spec=rfc2459.Certificate())[0]
        tbsCertificate = cert[0]
        subj = tbsCertificate['subject']
        validity = tbsCertificate['validity']
        extensions = tbsCertificate['extensions']

        dateformat = '%y%m%d%H%M%SZ'
        notBefore = datetime.strptime(str(validity.getComponentByPosition(0).getComponentByPosition(0)), dateformat)
        notAfter = datetime.strptime(str(validity.getComponentByPosition(1).getComponentByPosition(0)), dateformat)

        #print ('not before: ' + str(notBefore) + ', not after: ' + str(notAfter))

        now = datetime.utcnow()

        if now >= notBefore:
            if now <= notAfter:
                print ('Cert is still valid')
                valid = True
            else:
                print ('expired cert!')
        else:
            print ('cert not valid yet!')

    return valid

def checkSignature (request):
    sig = None
    certUrl = None
    
    try:
        sig = request.META['HTTP_SIGNATURE']
        certUrl = request.META['HTTP_SIGNATURECERTCHAINURL']
    except:
        print ('Signature or Signature Chan URL are missing from headers. See Alexa docs for more info')
        return False

    try:
        for retryCount in range(0,1):
            pem = loadCertPem(certUrl)
            if pem != None:
                certs = extractCerts(pem)

                # Decode the presented signature
                decodedSig = base64.b64decode(sig)

                # Generate a sha1 hash of the message body we received
                # in the original request payload
                myHash = generateHash(request.body)

                # check the signature against each presented cert
                for cert in certs:
                    rsa_key = extractPublicKey(cert)
                    try:
                        pkcs1_15.new(rsa_key).verify(myHash, decodedSig)
                        print ('Alexa signature of this request is valid')
                        return True
                    except:
                        print ('this cert failed when trying to verify..moving on to the next (if any) ')
            else:
                print ('error loading cert from ' + certUrl)
            
            # If we get here, it means something about sig check failed. 
            # Reload the cert, in case amazon swapped certs on us 
            print ('Reloading cert from Amazon, to retry sig check with fresh copy of cert')
            reloadCert(certUrl)
    except:
        print ('unable to validate signature')
    return False    

def loadCertPem (url):
    # check if we've cached this cert in /tmp already
    fileName = fileNameForCert(url)
    pemText = None

    if os.path.isfile(fileName):
        tmpPemText = None
        print ('Using cached copy of this cert')
        with open(fileName, 'r') as certFile:
            tmpPemText = certFile.read()
        certFile.close()

        if validateCertChain(tmpPemText):
            pemText = tmpPemText
        else:
            print('Cert chain could not be validated. Cert may be expired.')
    else:
        if validateCertUrl(url):
            pemText = reloadCert(url)
        else:
            print ('Cert URL did not pass validation: ' + url)


    return pemText

def fileNameForCert (url):
    return '/tmp/' + url.replace(':','-').replace('/','^').replace('.', '_') + '.pem'

def cacheCert (url, pemText):
    fileName = fileNameForCert(url)
    print ('Writing cert pem to ' + fileName)

    with open(fileName, 'w') as certFile:
        certFile.write(pemText)
    certFile.close()

def reloadCert (url):
    print ('Loading cert from ' + url)
    pemText = None
    response = requests.get(url)
    if response.status_code == 200:
        tmpPemText = response.text

        # Validate the cert chain
        if validateCertChain(tmpPemText):
            pemText = tmpPemText
            cacheCert (url, pemText)
        else:
            print ('Cert did not pass chain validation!')
    else:
        print ('Cert could not be retrieved from ' + certUrl)
    return pemText

def test():
    certUrl = 'https://s3.amazonaws.com/echo.api/echo-api-cert-4.pem'
    pemText = loadCertPem(certUrl)

    reloadCert(certUrl)

    #if validateCertUrl(certUrl):
    #    response = requests.get(certUrl)
    #    if response.status_code == 200:
    #        pem = response.text
    #        validateCertChain(pem)
    #        certs = extractCerts(pem)
    #        #extractCerts(pem)

if __name__ == "__main__":
    test()
