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
from ibm_cloud_sdk_core import get_authenticator_from_environment
old V1 ^^^^ '''
#speech-text APIS are still at V1 for now
from ibm_watson import SpeechToTextV1
from ibm_watson import TextToSpeechV1


assistant_svc = None
assistant_id = None
speech_to_text_svc = None
text_to_speech_svc = None

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
    global session_id, assistant_id, assistant_svc
    conv_text = request.form.get('convText') or 'hello'

    #new V2 vvvvv
    session_id = get_session()

    # coverse with WA Bot
    input = {
        'text': conv_text,
         'options': {'alternate_intents': True, 'return_context': True, 'debug': True }
    }    
    response = assistant_svc.message(
        assistant_id=assistant_id, 
        session_id=session_id, 
        input=input).get_result()
    #new V2 ^^^^
    """ old V1 vvvvv
    # load context if it exists
    convContext = request.form.get('context', "{}")
    context = json.loads(convContext)
    response = assistant.message(workspace_id=workspace_id,
                                 input={'text': conv_text},
                                 context=context)
    response = response.get_result()
    old V1 ^^^^^ """

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


    #intents = response["output"]["intents"]
    #for intent in intents:
    #    print(f'intent:  {intent["intent"]} confidence: {intent["confidence"]}')
    #entities = response["output"]["entities"]
    #for entity in entities:
    #    print(f'entity:  {entity["intent"]} confidence: {entity["confidence"]}')
    #print(f'skill {response["output"]["skills"]}')

    #delete session if explicit from user
    if (conv_text == "bye"):
        delete_session()
    return jsonify(results=response_details)


@app.route('/api/text-to-speech', methods=['POST'])
def getSpeechFromText():
    global text_to_speech_svc
    inputText = request.form.get('text')
    my_voice = request.form.get('voice', voice)

    def generate():
        if inputText:
            audioOut = text_to_speech_svc.synthesize(
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
    global speech_to_text_svc
    audio = request.get_data(cache=False)
    print(f'audio size is {len(audio)}')
    response = speech_to_text_svc.recognize(
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

#Note: this was in __main__, not a good idea, flask may not be started that way :)
@app.before_first_request
def before_first_request():
    global assistant_svc, assistant_id, speech_to_text_svc, text_to_speech_svc, voice, model
    #new V2 vvvvv
    #check for mandatory configuration. flask does load_dotenv() for us

    #Watson Assitant
    wa_apikey = checkenv('ASSISTANT_APIKEY')
    wa_url = checkenv('ASSISTANT_URL')
    assistant_id = checkenv('ASSISTANT_ID')
    assistant_version = checkenv("ASSISTANT_VERSION")
    authenticator = IAMAuthenticator(wa_apikey)

    print('Config:')
    print(f'   Watson version: {assistant_version} key: {wa_apikey}')
    print(f'   Watson url: {wa_url}')
    assistant_svc = AssistantV2( authenticator=authenticator, version=assistant_version)
    assistant_svc.set_service_url(wa_url)

    #remove - testing
    '''
    get_session()
    delete_session()
    '''

    #Speech to Text
    s2t_apikey =checkenv('SPEECH_TO_TEXT_APIKEY')
    s2t_url = checkenv('SPEECH_TO_TEXT_URL')
    model = checkenv("SPEECH_TO_TEXT_MODEL", 'en-US_BroadbandModel')
    authenticator = IAMAuthenticator(s2t_apikey)
    speech_to_text_svc = SpeechToTextV1(authenticator)
    speech_to_text_svc.set_service_url(s2t_url)

    print(f'   speech_to_text key: {s2t_apikey}')
    print(f'   speech_to_text url: {s2t_url}')

    # Text to Speech
    t2s_apikey = checkenv('TEXT_TO_SPEECH_APIKEY')
    t2s_url = checkenv('TEXT_TO_SPEECH_URL')
    voice = checkenv("TEXT_TO_SPEECH_VOICE", 'en-US_AllisonVoice')
    authenticator = IAMAuthenticator(t2s_apikey)
    text_to_speech_svc = TextToSpeechV1(authenticator)
    text_to_speech_svc.set_service_url(t2s_url)

    print(f'   text_to_speech key: {s2t_url}')
    print(f'   text_to_speech url: {t2s_url}')

    print(f'   model: {model} voice: {voice} ')
 

    #new V2 ^^^^
    """ old V1 vvvvv
    load_dotenv(verbose=True)
    # SDK is currently confused. Only sees 'conversation' for CloudFoundry.
    authenticator = (get_authenticator_from_environment('assistant') or
                     get_authenticator_from_environment('conversation'))

    assistant = AssistantV1(version=os.getenv("ASSISTANT_DATE"), authenticator=authenticator)
    workspace_id = assistant_setup.init_skill(assistant)
    old V1 ^^^^^ """

def checkenv(checkfor, default=None):
    required = os.environ.get(checkfor) or None
    if required != None:
        return required
    elif default != None:
        return default
    raise ValueError(f'{checkfor} not found in: environment, .env or .flaskenv - Correct config')

# create a new session if there, otherwise create
def get_session():
    global session_id
    if session_id != None:
        return session_id
    response = assistant_svc.create_session(assistant_id=assistant_id).get_result()
    session_id = response['session_id']
    print(f'Session created! {session_id}')
    return session_id

def delete_session():
    global session_id
    if session_id == None:
        return
    assistant_svc.delete_session(
        assistant_id=assistant_id,
        session_id=session_id).get_result()
    print(f'Session {session_id}deleted. Bye...')                       
    session_id = None



if __name__ == "__main__":
    print('hello from __main__')
    load_dotenv(verbose=True)
    port = os.environ.get("PORT") or os.environ.get("VCAP_APP_PORT") or 5000
    socketio.run(app, host='0.0.0.0', port=int(port))
    app.run(debug=True)
