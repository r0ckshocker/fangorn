"""CrowdStrike FalconPy Quick Start."""
from operator import contains
from falconpy import Hosts, HostGroup, APIHarness
from dotenv import load_dotenv
import json
import os

class CrowdStrikeClient():
    def __init__(self):
        load_dotenv()
        self.CROWDSTRIKE_API_CLIENT_ID = os.getenv("CROWDSTRIKE_API_CLIENT_ID")
        self.CROWDSTRIKE_API_SECRET = os.getenv("CROWDSTRIKE_API_SECRET")
        self.CROWDSTRIKE_LOCKDOWN_GROUP_ID = os.getenv("CROWDSTRIKE_LOCKDOWN_GROUP_ID")
        # self.IPINFO_TOKEN = get_or_throw("IPINFO_TOKEN")

    def falcon_connect(self):
        falcon = APIHarness(client_id=self.CROWDSTRIKE_API_CLIENT_ID,
                    client_secret=self.CROWDSTRIKE_API_SECRET,
                    base_url="https://api.us-2.crowdstrike.com",
                    )
        return falcon

    def falcon_host(self):
        falcon = Hosts(client_id=self.CROWDSTRIKE_API_CLIENT_ID,
                    client_secret=self.CROWDSTRIKE_API_SECRET,
                    base_url="https://api.us-2.crowdstrike.com",
                    )
        return falcon
    
    def falcon_host_group(self):
        falcon = HostGroup(client_id=self.CROWDSTRIKE_API_CLIENT_ID,
                    client_secret=self.CROWDSTRIKE_API_SECRET,
                    base_url="https://api.us-2.crowdstrike.com",
                    )
        return falcon

    # def get_ip_info(self, ip):
    #     URL = 'https://ipinfo.io/{}?token={}'.format(ip, self.IPINFO_TOKEN)
    #     response = requests.get(URL)
    #     return response.text

    def list_hosts(self):
        falcon = self.falcon_connect()
        result = falcon.command("QueryDevicesByFilter", limit=200, sort="hostname.asc")
        details = falcon.command("GetDeviceDetails", ids=result["body"]["resources"])
        return details["body"]["resources"]

    def cs_query(self, query):
        falcon = self.falcon_connect()
        aid_list = falcon.command("QueryDevicesByFilter", limit=200, filter=query)
        return aid_list["body"]["resources"]

    def get_user_info(self):
        falcon = self.falcon_connect()
        users = falcon.command("QueryDevicesByFilter", limit=200, sort="hostname.asc")
        BODY = {
            "ids": users["body"]["resources"]
        }
        response = falcon.command("QueryDeviceLoginHistory", body=BODY)
        return response["body"]["resources"]

    def host_action(self, action: str, host_id: list):
        PARAMS = {
        "action_name": action
        }

        BODY = {
            "ids": host_id
        }
        falcon = self.falcon_connect()
        response = falcon.command("PerformActionV2", parameters=PARAMS, body=BODY)
        print(response)

    def check_org(self, ip, org):
        ipinfo_data = json.loads(self.get_ip_info(ip))
        ipinfo_org = ipinfo_data['org']
        if org in str(ipinfo_org):
            return("Closing alerts because account is using expected IP range. IP: {} belongs to {}\n".format(ip, org))
        else:
            return("IP does not match the org provided. Requested org was {} but the IP {} belongs to {}".format(org, ip, ipinfo_org))
    
    def hostname(self, serial_number):
        SEARCH_FILTER = serial_number
        falcon = self.falcon_host()
        # Retrieve a list of hosts that have a hostname that matches our search filter
        hosts_search_result = falcon.QueryDevicesByFilter(filter=f"hostname:'{SEARCH_FILTER}'")
        return hosts_search_result

    def find_by_serial_number(self, serial_number):
        SEARCH_FILTER = serial_number
        falcon = self.falcon_host()
        # Retrieve a list of hosts that have a hostname that matches our search filter
        hosts_search_result = falcon.QueryDevicesByFilter(filter=f"serial_number:'{SEARCH_FILTER}'")
        return hosts_search_result
    

    def crowdstrike_ip(self, hostname):
        SEARCH_FILTER = hostname
        falcon = self.falcon_connect()
        # Retrieve a list of hosts that have a hostname that matches our search filter
        hosts_search_result = falcon.QueryDevicesByFilter(filter=f"hostname:'{SEARCH_FILTER}'")

        # Confirm we received a success response back from the CrowdStrike API
        if hosts_search_result["status_code"] == 200:
            hosts_found = hosts_search_result["body"]["resources"]
            # Confirm our search produced results
            if hosts_found:
                # Retrieve the details for all matches
                hosts_detail = falcon.get_device_details(ids=hosts_found)["body"]["resources"]
                for detail in hosts_detail:
                    # Display the AID and hostname for this match
                    aid = detail.get("device_id")
                    hostname = detail.get("hostname")
                    external_ip = detail.get("external_ip")
                    print(f"Host: {hostname} \n external ip: {external_ip} \n aid: {aid}")
                    return external_ip
            else:
                return "No hosts found matching that hostname within your Falcon tenant."
        else:
            # Retrieve the details of the error response
            error_detail = hosts_search_result["body"]["errors"]
            for error in error_detail:
                # Display the API error detail
                error_code = error["code"]
                error_message = error["message"]
                return(f"[Error {error_code}] {error_message}")

    def state_list(self, device_list):
        devices = device_list[2]
        device_count = len(devices)
        state_list = []
        falcon = self. falcon_connect()
        while device_count > 99:
            reduced_list = devices[device_count-99:device_count]
            response = falcon.get_online_state(ids=reduced_list)
            state_list.append(response["body"]["resources"])
            print(state_list)
            device_count-=100
        final_response = falcon.get_online_state(devices[:device_count])
        state_list.append(final_response["body"]["resources"])
        
        return state_list

    def get_device_details(self, host_id):
        falcon = self.falcon_connect()
        hosts_detail = falcon.get_device_details(ids=host_id).get("body").get("resources")
        return hosts_detail

    def get_device_ids(self):
        falcon = self.falcon_host()
        limit = 100
        total = 1
        offset = 0
        device_ids = []
        while offset < total:
            response = falcon.query_devices_by_filter(limit=limit, offset=offset)
            if response["status_code"] == 200:
                result = response["body"]
                offset = result["meta"]["pagination"]["offset"]
                total = result["meta"]["pagination"]["total"]
                device_ids.extend(result["resources"])
            else:
                raise Exception("Failed to retrieve device list")
        return device_ids

    def device_list(self):
        falcon = self.falcon_host()
        id_list = self.get_device_ids()
        response = falcon.get_device_details(ids=id_list)
        if response["status_code"] == 200:
            data = [x for x in response["body"]["resources"] if x["os_version"] not in ["Amazon Linux 2023", "Amazon Linux 2", "Linux", "Windows Server 2019"]]
            for item in data:
                item["serial"] = item.get("serial_number") or item.get('hostname')
                item["hostname_cs"] = item.get('hostname')
                item["last_seen_cs"] = item.get("last_seen")
                item["user_cs"] = item.get("last_login_user")
                item["model_cs"] = item.get("system_product_name")
            return data
        else:
            raise Exception("Failed to retrieve device details")

    def update_host_group(self, action, host_id, group_id):
        falcon = self.falcon_host_group()
        act_params = [{
            "name": "id", 
            "value": group_id
        }]

        if not isinstance(host_id, list):
            host_id = [host_id]

        response = falcon.performGroupAction(action_name=action, # add-hosts or remove-hosts
                                     ids=host_id, #string or list of strings
                                     action_parameters=act_params
                                     )
        return response
    
    def lockdown(self, host_id):
        response = self.update_host_group("add-hosts", host_id, self.CROWDSTRIKE_LOCKDOWN_GROUP_ID)
        return response