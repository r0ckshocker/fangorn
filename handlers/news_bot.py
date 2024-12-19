from common import slack_api
import json
import requests

oracle_header = "Recent News"

HN_API_URL = "https://hacker-news.firebaseio.com/v0"
HN_URL = "https://news.ycombinator.com/"

## TODO: create list of sites to pull news from
# news_sites = [
#     hacker_news : {"https://hacker-news.firebaseio.com/v0/topstories.json" : "https://news.ycombinator.com"}, 
#     cloud_news : {" ":" "}, 
#     ai_news : {" ":" "}, 
#     pharma_news : {" ":" "}
# ]

STORIES_NUMBER = 5

## TODO: use the below functions to pull news from sites in list above
## Fetch details for a single story
def fetch(session, url):
    with session.get(url) as response:
        if response.status_code != 200:
            response.raise_for_status()
        response = response.text
        return json.loads(response)
    
## Fetch details for all top stories
def fetch_all(urls):
    with requests.Session() as session:
        tasks = []
        for url in urls:
            task = session.get(url)
            tasks.append(task)
        results = [fetch(session, url) for url in urls]
        return results

def get_top_stories():
    stories = requests.get(f"{HN_API_URL}/topstories.json")
    stories_ids = json.loads(stories.text)
    urls = [f"{HN_API_URL}/item/{story_id}.json" for story_id in stories_ids[:STORIES_NUMBER]]
    fetched_stories = fetch_all(urls)
    sorted_stories = sorted(fetched_stories, key=lambda k: k["score"], reverse=True)
    
    # Trimmer to only include the following keys
    trimmed_stories = []
    for story in fetched_stories:
        trimmed_story = {}
        for key in ["by", "id", "score", "time", "title", "type", "url"]:
            trimmed_story[key] = story.get(key)
        trimmed_stories.append(trimmed_story)
    return trimmed_stories

## TODO: get the most recent articles posted from sites that dont have score
## since CrowdStrike and Orca don't have scores for their articles,
#  we will can get the most recent articles
# def get_recent_stories(url):
#     stories = requests.get(url)
#     stories_ids = json.loads(stories.text)
#     # urls = [f"{url}/item/{story_id}.json" for story_id in stories_ids[:STORIES_NUMBER]]
#     fetched_stories = fetch_all(urls)
#     sorted_stories = sorted(fetched_stories, key=lambda k: k["time"], reverse=True)
#     return sorted_stories

# TODO: Create slack text with top stories and post message to slack channel via newsbot
def create_hn_text():
    """Create slack text with HackerNews top stories"""
    text_list = [f"Top {STORIES_NUMBER} from HackerNews:"]
    sorted_stories = get_top_stories()
    # Format slack text
    for story in sorted_stories:
        text_list.append(
            "*<{}|{}>* - <{}|{}>".format(
                "{}/item?id={}".format(HN_URL, story["id"]),
                story["score"],
                # Ask HN type posts do not have 'url' key, so using get to return None
                story.get('url'),
                story["title"],
            )
        )
    return "\n>".join(text_list)

def handler(event, context):
    slack_api.send_message(slack_api.simple_message(create_hn_text(),oracle_header))

if __name__ == '__main__':
    slack_api.send_message(slack_api.simple_message(create_hn_text(),oracle_header))
