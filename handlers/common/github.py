import requests
import json
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def get_alerts(url, headers):
    alerts = []
    count_pages = 0

    try:
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            alerts += response.json()
            count_pages = 1

            while 'Link' in response.headers and 'rel="next"' in response.headers['Link']:
                next_page_url = None
                for link in response.headers['Link'].split(','):
                    if 'rel="next"' in link:
                        next_page_url = link[link.index('<')+1:link.index('>')]
                        break
                if next_page_url:
                    response = requests.get(next_page_url, headers=headers)
                    if response.status_code == 200:
                        alerts += response.json()
                        count_pages += 1
                        logger.info(f"Added one more page, total of pages is now {count_pages}, onto the next")
                    else:
                        logger.error(f"Failed to fetch next page: {response.status_code} - {response.text}")
                        break
                else:
                    break
            logger.info(f"{count_pages} pages of alerts have been downloaded")
        else:
            logger.error(f"Error fetching alerts: {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"Exception occurred while fetching alerts: {e}")

    return alerts

def clean_alerts(blob, trim_alert):
    alerts = []
    try:
        for alert in blob:
            trimmed_alert = trim_alert(alert)
            alerts.append(trimmed_alert)
        logger.info(f"{len(alerts)} alerts have been trimmed")
    except Exception as e:
        logger.error(f"Exception occurred while cleaning alerts: {e}")
    return alerts

def get_counts(alerts, keys):
    counts = []
    try:
        for key in keys:
            values = list({alert.get(key) for alert in alerts})
            for value in values:
                count = sum(1 for alert in alerts if alert.get(key) == value)
                counts.append({'key': key, 'value': value, 'count': count})
    except Exception as e:
        logger.error(f"Exception occurred while getting counts: {e}")

    return counts
