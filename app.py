# -*- coding: utf-8 -*-
# Copyright 2018 IBM Corp. All Rights Reserved.

# Licensed under the Apache License, Version 2.0 (the “License”)
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#  https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an “AS IS” BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, Response
from flask import jsonify
from flask import request, redirect
from flask_socketio import SocketIO
from flask_cors import CORS
#new for V2 vvvvv
from ibm_watson import AssistantV2
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
#new for V2 ^^^^^
#speech-text APIS are still at V1 for now
from ibm_watson import SpeechToTextV1
from ibm_watson import TextToSpeechV1

# get from environment, default or exception
def checkenv(checkfor, default=None):
    required = os.environ.get(checkfor) or None
    if required != None:
        return required
    elif default != None:
        return default
    raise ValueError(f'{checkfor} not found in: environment, .env or .flaskenv - Correct config')     

'''
WatsonConnector ia a collection of API objects and a chat recorder utility.
The API objects are shared by all users you may have
'''
class WatsonConnector:
    def __init__(self):
        pass #do it all after Flask loaded, .flaskenv pulled in

    def load_before(self):
        #check for mandatory configuration. 

        #Note: some of the  API Details supplied by IBM append the version and key details.  
        # The IBM implemnation passes the key in as a parameter and builds up the 
        # complete URL.  If you pass in what is supplied, version and key are  duplicated and causes 
        # errors.  To avoid duplication and an invlaid URL,  truncate the version and everyting after it.

        #Watson Assitant
        self.wa_apikey = checkenv('ASSISTANT_APIKEY')
        self.wa_url = checkenv('ASSISTANT_URL').split('/v')[0] #truncate version
        self.assistant_id = checkenv('ASSISTANT_ID')
        self.assistant_version = checkenv("ASSISTANT_VERSION")
        authenticator = IAMAuthenticator(self.wa_apikey)
        record = checkenv("ASSISTANT_RECORD", "NO").lower()
        if record[0] in ['n', 'y', 'u']: # record n-none, y-yes to all, u- yes to unkown(Watson does not recognize)
            self.record_questions = record[0]
            self.chatlog = checkenv("ASSISTANT_RECORD_FILE", 'chatlog.csv')
            Path(self.chatlog).touch() #if create/access problems File???Error gets raised now
        else:
            self.record_questions = 'n'


        print('Config:')
        print(f'   Watson version: {self.assistant_version} key: {self.wa_apikey}')
        print(f'   Watson url: {self.wa_url}')
        self.assistant_api = AssistantV2( authenticator=authenticator, version=self.assistant_version)
        self.assistant_api.set_service_url(self.wa_url)

        #Speech to Text
        self.s2t_apikey =checkenv('SPEECH_TO_TEXT_APIKEY')
        self.s2t_url = checkenv('SPEECH_TO_TEXT_URL').split('/v')[0] #truncate version
        authenticator = IAMAuthenticator(self.s2t_apikey)
        self.speech_to_text = SpeechToTextV1(authenticator)
        self.speech_to_text.set_service_url(self.s2t_url)

        print(f'   speech_to_text key: {self.s2t_apikey}')
        print(f'   speech_to_text url: {self.s2t_url}')

        # Text to Speech
        self.t2s_apikey = checkenv('TEXT_TO_SPEECH_APIKEY')
        self.t2s_url = checkenv('TEXT_TO_SPEECH_URL').split('/v')[0] #truncate version 
        authenticator = IAMAuthenticator(self.t2s_apikey)
        self.text_to_speech = TextToSpeechV1(authenticator)
        self.text_to_speech.set_service_url(self.t2s_url)

        print(f'   text_to_speech key: {self.t2s_apikey}')
        print(f'   text_to_speech url: {self.t2s_url}')




    def record_chat(self, conv_text, response_txt, entities):
        if self.record_questions == 'n':
            return
        elif self.record_questions == 'u' and len(entities) <= 0:
            return
        with open(self.chatlog,'a') as fd:
            # Watson identified, we want to know what and confidence
            if len(entities) > 0:
                ln = f'{conv_text},{response_txt}'
                news = [f'{entity["entity"]}:{entity["value"]}:{entity["confidence"]}' for entity in entities]
                ln += ',' + ','.join(news)
            # request was unidentified, don't need to know response text
            else:
                ln = conv_text
    
            ln.replace('\n', ' ')
            ln.replace(',', '|')
            fd.write(f'{ln}\n')        

'''
WatsonSession is a long running session between a specific user and the Watson Assistant.
The sessions have context and timpout logic
'''

class WatsonSession:
    def __init__(self, watson_connector):
        self.wc = watson_connector
        self.session_id = None
        pass #do rest after Flask loaded, .flaskenv pulled in

    def load_before(self):
        self.timeout = int(checkenv("ASSISTANT_TIMEOUT", 255))
        self.last_access = datetime.now() - timedelta(seconds=self.timeout + 10)   
        self.voice = checkenv("TEXT_TO_SPEECH_VOICE", 'en-US_AllisonVoice')
        self.model = checkenv("SPEECH_TO_TEXT_MODEL", 'en-US_BroadbandModel')
        print(f'   model: {self.model} voice: {self.voice} ')


    # create a new session if not there, otherwise return active
    def get_session(self):
        now = datetime.now()
        elapsed = now - self.last_access
        if elapsed.total_seconds() > self.timeout:
            self.session_id = None   #no need to delete, its gone already

        self.last_access = now

        if self.session_id != None:
            return self.session_id
        response = wconn.assistant_api.create_session(assistant_id=wconn.assistant_id).get_result()
        self.session_id = response['session_id']
        print(f'Session created! {self.session_id}')
        return self.session_id

    def delete_session(self):
        if self.session_id == None:
            return
        try:
            wconn.assistant_api.delete_session(
                assistant_id=wconn.assistant_id,
                session_id=self.session_id).get_result()
            print(f'Session {self.session_id}deleted. Bye...')
        except:
            pass                    
        self.session_id = None


app = Flask(__name__)
socketio = SocketIO(app)
CORS(app)
wconn = WatsonConnector()
wsess = WatsonSession(wconn)


# Redirect http to https on CloudFoundry
@app.before_request
def before_request():
    fwd = request.headers.get('x-forwarded-proto')

    # Not on Cloud Foundry
    if fwd is None:
        return None
    # On Cloud Foundry and is https
    elif fwd == "https":
        return None
    # On Cloud Foundry and is http, then redirect
    elif fwd == "http":
        url = request.url.replace('http://', 'https://', 1)
        code = 301
        return redirect(url, code=code)


@app.route('/')
def Welcome():
    return app.send_static_file('index.html')

@app.route('/api/conversation', methods=['POST', 'GET'])
def getConvResponse():
    #global session_id, assistant_id, assistant_api
    conv_text = request.form.get('convText') or 'hello'

    # coverse with WA Bot
    input = {
        'text': conv_text,
         'options': {'alternate_intents': True, 'return_context': True, 'debug': True }
    }    
    try:
        response = wconn.assistant_api.message(
            assistant_id=wconn.assistant_id, 
            session_id=wsess.get_session(), 
            input=input).get_result()
    except:
        wsess.delete_session()
        return jsonify(results={
            'responseText': 'session failed, retry',
            'context': ''
        })


    print(json.dumps(response, indent=2))

    response_txt = []
    for item in response["output"]["generic"]:
        response_txt.append(item["text"])
    if isinstance(response_txt, list):
        response_txt = '... '.join(response_txt)
    response_details = {
        'responseText': response_txt,
        'context': response["context"]
    }

    wconn.record_chat(conv_text, response_txt, response["output"]["entities"])


    #delete session if explicit from user
    if (conv_text == "bye"):
        wsess.delete_session()
    return jsonify(results=response_details)


@app.route('/api/text-to-speech', methods=['POST'])
def get_speech_from_text():

    input_text = request.form.get('text')
    my_voice = request.form.get('voice', wsess.voice)
    print(f'get_speech_from_text - input: {input_text} len {len(input_text)} voice: {my_voice}')

    def generate():
        if input_text:
            audio_out = wconn.text_to_speech.synthesize(
                text=input_text,
                accept='audio/wav',
                voice=my_voice).get_result()

            data = audio_out.content
        else:
            print("Empty response")
            data = "I have no response to that."

        yield data

    return Response(response=generate(), mimetype="audio/x-wav")


@app.route('/api/speech-to-text', methods=['POST'])
def getTextFromSpeech():
    audio = request.get_data(cache=False)
    print(f'audio size is {len(audio)}')
    response = wconn.speech_to_text.recognize(
            audio=audio,
            content_type='audio/wav',
            timestamps=True,
            word_confidence=True,
            smart_formatting=True).get_result()

    # Ask user to repeat if STT can't transcribe the speech
    if len(response['results']) < 1:
        return Response(mimetype='plain/text',
                        response="Sorry, didn't get that. please try again!")

    text_output = response['results'][0]['alternatives'][0]['transcript']
    text_output = text_output.strip()
    return Response(response=text_output, mimetype='plain/text')



@app.before_first_request
def before_first_request():
    #delayed so Flask env loaded
    wconn.load_before()
    wsess.load_before()


if __name__ == "__main__":
    print('hello from __main__')
    port = os.environ.get("PORT") or os.environ.get("VCAP_APP_PORT") or 5000
    socketio.run(app, host='0.0.0.0', port=int(port))
    app.run(debug=True)
