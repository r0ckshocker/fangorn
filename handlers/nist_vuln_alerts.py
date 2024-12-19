from common import slack_api
from datetime import datetime, timedelta
import os
import requests

oracle_header = "Daily CVE Alert"

# Creates current timestamp
today = datetime.now().date()
date_time = today.strftime("%m-%d-%Y-%H-%M-%S")
date_today = today.strftime("%Y-%m-%d")

# Pulls the CVEs from NVD in the past 24 hours
def get_cves():
    print("searching for New/modified CVES in the past day")
    time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    delta = datetime.now() - timedelta(days=1)
    yestarday = delta.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    nvd_api_token = os.getenv('NVD_API_TOKEN')
    cve_url = 'https://services.nvd.nist.gov/rest/json/cves/2.0/'
    headers = {'apiKey': nvd_api_token, }
    params = {
        "lastModStartDate": yestarday,
        "lastModEndDate": time,
    }
    response = requests.get(cve_url, headers=headers, params=params)
    # Check if request was successful
    if response.status_code == 200:
        # Parse JSON response
        all_cves = response.json()
        count_pages = 1
        total_cves = all_cves["totalResults"]
        severity_counts = {'critical_count': 0,'high_count': 0, 'medium_count': 0, 'low_count': 0}
        id_list = []
        score_list = []
        descriptions_list = []

        for cve in all_cves["vulnerabilities"]:
            c = cve["cve"]
            if "cvssMetricV31" in c["metrics"]:
                # Counts of each severity (some cves dont have v31 metric)
                cvss = c["metrics"]["cvssMetricV31"][-1]["cvssData"]["baseSeverity"]
                if cvss == "CRITICAL":
                    severity_counts['critical_count'] += 1
                elif cvss == "HIGH":
                    severity_counts['high_count'] += 1
                elif cvss == "MEDIUM":
                    severity_counts['medium_count'] += 1
                elif cvss == "LOW":
                    severity_counts['low_count'] += 1

                # Finding top 5 cve's with highest expoilt score * impact score
                exploitability_score = c["metrics"]["cvssMetricV31"][-1]["exploitabilityScore"]
                impact_score = c["metrics"]["cvssMetricV31"][-1]["impactScore"]
                total_score = exploitability_score * impact_score
                id_list.append(c["id"])
                score_list.append(total_score)
                d = c["descriptions"][0]["value"].split(". ")
                descriptions_list.append(d[0])

        # Combines the two lists into a list of tuples, then extracts the top 5 CVE's
        combined_list = list(zip(id_list, score_list, descriptions_list))
        sorted_list = sorted(combined_list, key=lambda x: x[1], reverse=True)
        top_5_cves = sorted_list[:5]

        # Dumps top 5 CVE's into two lists, one for ID's and one for scores
        # Makes it easier to format the slack message
        cve_ids = []
        cve_scores = []
        exploit_description = []
        i = 0
        if i < 5:
            for cve in top_5_cves:
                cve_ids.append(cve[0])
                cve_scores.append(cve[1])
                description = cve[2].strip()
                exploit_description.append(description.replace("\n", " "))
                i += 1
                results = {'total_cves': total_cves, 'severity_counts': severity_counts,
                           'cve_ids': cve_ids, 'cve_scores': cve_scores, 'exploit_decription': exploit_description}
        return results
    else:
        print(f'Error: {response.status_code} - {response.text}')

# Create a format for slack meassage
def cve_text_format():
    results = get_cves()
    text_list = ["*" + str(results['total_cves']) + "*" + " CVE's were disclosed in the past 24 hours:" + "\n"]
    text_list.append(
        "{}{}{}{}{}{}{}{}{}{}{}".format(
            "*Severity Level Counts:*" + "\n",
            "\t" + "Critical: " + str(results['severity_counts']['critical_count']) + "\t",
            "High: " + str(results['severity_counts']['high_count']) + "\n",
            "\t" + "Medium: " + str(results['severity_counts']['medium_count']) + "\t",
            "Low: " + str(results['severity_counts']['low_count']) + "\n",
            "*Top CVE's based on total score:*" + "\n",
            "\t" + "<https://nvd.nist.gov/vuln/detail/" + str(results['cve_ids'][0]) + "|" + "(" + str(results['cve_ids'][0]) + ") " + ">" + str(results['exploit_decription'][0])  + "\n",
            "\t" + "<https://nvd.nist.gov/vuln/detail/" + str(results['cve_ids'][1]) + "|" + "(" + str(results['cve_ids'][1]) + ") " + ">" + str(results['exploit_decription'][1])  + "\n",
            "\t" + "<https://nvd.nist.gov/vuln/detail/" + str(results['cve_ids'][2]) + "|" + "(" + str(results['cve_ids'][2]) + ") " + ">" + str(results['exploit_decription'][2])  + "\n",
            "\t" + "<https://nvd.nist.gov/vuln/detail/" + str(results['cve_ids'][3]) + "|" + "(" + str(results['cve_ids'][3]) + ") " + ">" + str(results['exploit_decription'][3])  + "\n",
            "\t" + "<https://nvd.nist.gov/vuln/detail/" + str(results['cve_ids'][4]) + "|" + "(" + str(results['cve_ids'][4]) + ") " + ">" + str(results['exploit_decription'][4])  + "\n",
        )
    )
    return "\n".join(text_list)

def handler(event, context):
    results = get_cves()
    slack_api.send_message(slack_api.simple_message(cve_text_format(),oracle_header))

if __name__ == '__main__':
    slack_api.send_message(slack_api.simple_message(cve_text_format(),oracle_header))