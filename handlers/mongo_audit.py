import logging
from common import dd, helper
from requests.auth import HTTPDigestAuth
import requests
import datetime
from dotenv import load_dotenv
import json

ATLAS_EVENT_KEY = helper.get_or_throw('ATLAS_EVENT_KEY')
ATLAS_EVENT_SECRET = helper.get_or_throw('ATLAS_EVENT_SECRET')
DD_API_KEY = helper.get_or_throw('DD_API_KEY')
DD_APP_KEY = helper.get_or_throw('DD_APP_KEY')
ATLAS_ORG_ID = helper.get_or_throw('ATLAS_ORG_ID')

# Get the groups in Atlas

def get_groups():  
    load_dotenv()  
  
    URL = "https://cloud.mongodb.com"  
    GROUPS_URI = "/api/atlas/v1.0/groups"  
  
    url = URL + GROUPS_URI  

    try:  
        response = requests.get(url, auth=HTTPDigestAuth(ATLAS_EVENT_KEY, ATLAS_EVENT_SECRET))  
        response.raise_for_status()  
        data = json.loads(response.text)  
        results = data['results']  
        return results  
    except requests.exceptions.HTTPError as e:  
        print(f"get_groups() - Error fetching groups: {e}") 

# Get the alerts for the groups above


def get_group_alerts():
    groups = get_groups()
    for group in groups:
        group_links = group.get('links')
        if group_links:
            for link in group_links:
                mins_ago = datetime.datetime.now() - datetime.timedelta(minutes=15)
                url = link['href'] + "/events/?minDate=" + mins_ago.isoformat()
                try:
                    response = requests.get(url, auth=HTTPDigestAuth(
                        ATLAS_EVENT_KEY, ATLAS_EVENT_SECRET))
                    response.raise_for_status()
                    results = response.json().get('results')
                    if results:
                        for r in results:
                            title = r.get('eventTypeName')
                            r = str(r)[:4000]
                            description = r
                            tags = 'atlas'
                            response = dd.post_dd_event(ddsource="Mongo Atlas",title=title, message=description, tags=tags, service="Atlas database")
                            print(f"Alert posted: {response}")
                except requests.exceptions.HTTPError as e:
                    print(
                        f"Error fetching alerts from group {link['href']}: {e}")

# Get org level alerts


def get_org_alerts():
    ORG_ID = ATLAS_ORG_ID
    ORG_URI = "/api/atlas/v1.0/orgs/{}/events".format(ORG_ID)
    URL = "https://cloud.mongodb.com"

    mins_ago = datetime.datetime.now() - datetime.timedelta(minutes=15)
    url = URL + ORG_URI + "/?minDate=" + mins_ago.isoformat()
    try:
        response = requests.get(url, auth=HTTPDigestAuth(
            ATLAS_EVENT_KEY, ATLAS_EVENT_SECRET))
        response.raise_for_status()
        file_name = "test_files/" + ORG_ID + "_" + mins_ago.isoformat() + ".json"
        results = response.json().get('results')
        if results:
            for r in results:
                title = r.get('eventTypeName')
                description = r
                tags = 'atlas'
                response = dd.post_dd_event(ddsource="Mongo Atlas",title=title, message=description, tags=tags, service="Atlas database")
                print(f"Alert posted: {response}")
    except requests.exceptions.HTTPError as e:
        print(f"Error fetching org level alerts: {e}")


def handler(event, context):
    ATLAS_EVENT_KEY = helper.get_or_throw('ATLAS_EVENT_KEY')
    ATLAS_EVENT_SECRET = helper.get_or_throw('ATLAS_EVENT_SECRET')
    DD_API_KEY = helper.get_or_throw('DD_API_KEY')
    DD_APP_KEY = helper.get_or_throw('DD_APP_KEY')
    ATLAS_ORG_ID = helper.get_or_throw('ATLAS_ORG_ID')
    print(event)
    print(context)
    get_group_alerts()
    get_org_alerts()
