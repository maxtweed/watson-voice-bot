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
''' old V1 vvvv
from ibm_watson import AssistantV1
import assistant_setup
old V1 ^^^^ '''
from ibm_watson import SpeechToTextV1
from ibm_watson import TextToSpeechV1
from ibm_cloud_sdk_core import get_authenticator_from_environment


assistant = None
assistant_service = None
assistant_id = None

#later - make these cookies, user session specific
session_id = None
voice = None
model = None


app = Flask(__name__)
socketio = SocketIO(app)
CORS(app)


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
    global session_id, assistant_id, assistant_service
    # load context if it exists
    convText = request.form.get('convText')
    convContext = request.form.get('context', "{}")
    context = json.loads(convContext)

    # create a new session if there, otherwise create
    #new V2 vvvvv
    if session_id == None:
        response = assistant_service.create_session(assistant_id=assistant_id).get_result()
        session_id = response['session_id']
        print(f'Session created! {session_id}\n')

    # coverse with WA Bot
    input = {
        'text': convText,
         'options': {'alternate_intents': True, 'return_context': True, 'debug': True }
    }    
    response = assistantService.message(assistant_id=assistant_id, session_id=session_id, input=input).get_result()
    #new V2 ^^^^
    """ old V1 vvvvv
    response = assistant.message(workspace_id=workspace_id,
                                 input={'text': convText},
                                 context=context)
    response = response.get_result()
    old V1 ^^^^^ """

    reponseText = response["output"]["text"]
    responseDetails = {'responseText': '... '.join(reponseText),
                       'context': response["context"]}

    #delete session if explicit from user
    if (convText == "bye"):
        response = assistantService.delete_session(
            assistant_id=assistant_id,
            session_id=session_id).get_result()
        session_id = None
        print('Session deleted. Bye...')                       
    return jsonify(results=responseDetails)


@app.route('/api/text-to-speech', methods=['POST'])
def getSpeechFromText():
    inputText = request.form.get('text')
    my_voice = request.form.get('voice', voice)
    ttsService = TextToSpeechV1()

    def generate():
        if inputText:
            audioOut = ttsService.synthesize(
                inputText,
                accept='audio/wav',
                voice=my_voice).get_result()

            data = audioOut.content
        else:
            print("Empty response")
            data = "I have no response to that."

        yield data

    return Response(response=generate(), mimetype="audio/x-wav")


@app.route('/api/speech-to-text', methods=['POST'])
def getTextFromSpeech():

    sttService = SpeechToTextV1()

    response = sttService.recognize(
            audio=request.get_data(cache=False),
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

#Note: this was in __main__, not a good idea, flask may not be started that way :)
@app.before_first_request
def before_first request():
    global authenticator, assistant_service, assistant_id, voice, model

    #check for stuff that must be configured. flask does load_dotenv() for us
    stock_error = 'not found in environment, .env or .flaskenv'
    apikey = os.environ.get('ASSISTANT_APIKEY') or None
    if apikey == None:
        raise ValueError(f'ASSISTANT_APIKEY {stock_error}')
    assistant_id = os.environ.get('ASSISTANT_ID')
    if assistant_id == None:
        raise ValueError(f'ASSISTANT_ID {stock_error}')
    url = os.environ.get('ASSISTANT_URL') or None
    if url == None:
        raise ValueError(f'ASSISTANT_URL {stock_error}')
    assistant_version = os.getenv("ASSISTANT_VERSION") or None
    if assistant_version == None:
        raise ValueError(f'ASSISTANT_VERSION {stock_error}')

    voice = os.getenv("TEXT_TO_SPEECH_VOICE") or 'en-US_AllisonVoice'
    model = os.getenv("SPEECH_TO_TEXT_MODEL") or 'en-US_BroadbandModel'

    print(f'version {assistant_version} key: {apikey} url: {url}')
    print(f'model {model} voice: {apikvoiceey} assistant_version: {assistant_version}')
    #new V2 vvvvv

    #get authenticator using apikey, get assisant_service, set url
    authenticator = IAMAuthenticator(apikey)
    print(f'authenticator {authenticator}')
 
    assistant_service = AssistantV2( authenticator=authenticator, version=assistant_version)
    assistant_service.set_service_url(url)
    #new V2 ^^^^
    """ old V1 vvvvv
    load_dotenv(verbose=True)
    # SDK is currently confused. Only sees 'conversation' for CloudFoundry.
    authenticator = (get_authenticator_from_environment('assistant') or
                     get_authenticator_from_environment('conversation'))

    assistant = AssistantV1(version=os.getenv("ASSISTANT_DATE"), authenticator=authenticator)
    workspace_id = assistant_setup.init_skill(assistant)
    old V1 ^^^^^ """

    port = os.environ.get("PORT") or os.environ.get("VCAP_APP_PORT") or 5000
    socketio.run(app, host='0.0.0.0', port=int(port))
