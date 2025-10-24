

import sqlalchemy
import os
from dotenv import load_dotenv
import json
import requests

load_dotenv()

def sql_engine():

    # path=file+db
    # engine = create_engine(path)
    db_url = os.getenv('db_url')
    engine = sqlalchemy.create_engine(db_url, encoding="utf8",
                                      echo=False)

    return engine



def send_notice(event_name, payload):

    load_dotenv()

    ifttt_key = os.getenv('IFTTT_KEY')

    
    ifttt_key_funding_notify = ifttt_key
    key = ifttt_key_funding_notify
    # url = "https://maker.ifttt.com/trigger/"+event_name+"/with/key/"+key+""
    url = "https://maker.ifttt.com/trigger/"+event_name+"/json/with/key/"+key+""
    payload = {
        "address": "ssss",
    }
    # payload = "{\n    \"value1\": \""+text+"\"\n, \"value2\": \""+text2+"\"\n}"
    headers = {
    'Content-Type': "application/json",
    'User-Agent': "PostmanRuntime/7.15.0",
    'Accept': "*/*",
    'Cache-Control': "no-cache",
    'Postman-Token': "a9477d0f-08ee-4960-b6f8-9fd85dc0d5cc,d376ec80-54e1-450a-8215-952ea91b01dd",
    'Host': "maker.ifttt.com",
    'accept-encoding': "gzip, deflate",
    'content-length': "63",
    'Connection': "keep-alive",
    'cache-control': "no-cache"
    }
 
    requests.request("POST", url, data=json.dumps(payload).encode('utf-8'), headers=headers)



