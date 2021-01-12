# .flaskenv has public flask environment variables, such as api URLs, versions, ...  define api keys in .env

# Watson Assistant
ASSISTANT_VERSION=2020-04-01
#ASSISTANT_API_VERSION=versionV2
ASSISTANT_TIMEOUT=255   # in seconds.  std: 5 minutes, premium 1hr+ see https://cloud.ibm.com/docs/assistant?topic=assistant-assistant-settings
ASSISTANT_URL=https://api.us-south.assistant.watson.cloud.ibm.com/instances/df936c75-d181-4bc7-a7f4-a5376ec06001/v2/assistants/4dfee9fa-dfa9-42f9-9eb6-43d7db67424f/sessions
ASSISTANT_RECORD=YES # NO, YES (all), UNKNOWN(questions Watson does not recognize)
ASSISTANT_RECORD_FILE=chatlog.csv
 
# Watson Speech to Text
SPEECH_TO_TEXT_URL=https://api.us-south.speech-to-text.watson.cloud.ibm.com/instances/9b16979a-3ebf-402e-af32-886422cb6ef9
SPEECH_TO_TEXT_MODEL=en-US_BroadbandModel

# Watson Text to Speech
TEXT_TO_SPEECH_URL=https://api.us-south.text-to-speech.watson.cloud.ibm.com/instances/b94e1bb8-b251-4926-94fc-7afd063ab52a
TEXT_TO_SPEECH_VOICE=en-US_AllisonVoice


