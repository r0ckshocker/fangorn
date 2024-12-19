from common.crowdstrike import CrowdStrikeClient
from common.reftab import ReftabClient
from common.jamf import jamf
import json

def handler(event, context):
    cs_client = CrowdStrikeClient()
    jamf_client = jamf.Jamf()
    rt_client = ReftabClient()
    for user in event.get('users'):
        resposne = jamf_client.get_computers_assigned_to_user(user.get('username'))
        jamf_ids = [computer.get('id') for computer in resposne]
        serial_numbers = [computer.get('serial_number') for computer in resposne]
        for serial_number in serial_numbers:
            if user.get('quarantine'):
                host_id = cs_client.find_by_serial_number(serial_number)
                cs_client.update_host_group('add-host',host_id, cs_client.CROWDSTRIKE_QUARANTINE_GROUP_ID) #need to create a quarantine group
                print(f"Quarantine {host_id}")
            if user.get('lockdown'):
                host_id = cs_client.find_by_serial_number(serial_number)
                cs_id = host_id.get('body').get('resources')[0]
                cs_client.update_host_group(action='add-host',host_id=cs_id, group_id=cs_client.CROWDSTRIKE_LOCKDOWN_GROUP_ID)
                print(f"Lockdown {host_id}")
            
        for jamf_id in jamf_ids:
            info = jamf_client.get_computer_inventory_by_id(jamf_id)
            general = json.loads(info).get('general', {})
            management_id = general.get('managementId')
            print(management_id)
            erased = jamf_client.erase_device(management_id)
            print(erased)
        #update = rt_client.update_user(user.get('username'), {'computers': resposne})
    return {"message": "Complete", "status": 200}
