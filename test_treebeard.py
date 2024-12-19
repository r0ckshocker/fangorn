import requests
import logging
import json
import time
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Configure logging
logging.basicConfig(level=logging.INFO, filename='test.log', filemode='w',
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Base URLs for the API and health check
BASE_URL = 'http://localhost:8080/api'
HEALTHZ_URL = 'http://localhost:8080/healthz'
TEST_FILE_PATH = "test_analysis.txt"

# List of oracles to test
oracles = [
    {"dashboard_id": "alfred", "name": "home"},
    {"dashboard_id": "env_config", "name": "envconfig"},
    {"dashboard_id": "devision", "name": "devision"},
    {"dashboard_id": "lucius", "name": "lucius"}
]

# Test user information
TEST_USER = {
    "name": "Test User",
    "email": "test@example.com"
}

# Dictionary to store test results
test_results = {
    "summary": {
        "pass_count": 0,
        "fail_count": 0
    },
    "details": []
}

def create_session():
    session = requests.Session()
    retries = Retry(total=5, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504, 529])
    session.mount('http://', HTTPAdapter(max_retries=retries))
    session.mount('https://', HTTPAdapter(max_retries=retries))
    return session

def log_test_result(test_name, status, message="", responses=None):
    result = {
        "test_name": test_name,
        "status": status,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "message": message,
        "responses": responses or []
    }
    test_results["details"].append(result)
    if status == "pass":
        test_results["summary"]["pass_count"] += 1
    else:
        test_results["summary"]["fail_count"] += 1
    logger.info(f"Test {test_name}: {status} - {message}")

def test_healthz(session):
    test_name = "test_healthz"
    try:
        response = session.get(HEALTHZ_URL, timeout=15)
        if response.status_code == 200:
            log_test_result(test_name, "pass", responses=[response.json()])
            return True
        else:
            log_test_result(test_name, "fail", response.text)
            return False
    except Exception as e:
        log_test_result(test_name, "fail", str(e))
        return False

def trim_dashboard_data(data):
    """Helper function to trim dashboard data to first 3 and last 3 items."""
    if not isinstance(data, dict):
        return data

    if "apps" in data and isinstance(data["apps"], dict):
        apps = data["apps"]
        if len(apps) > 6:
            items = list(apps.items())
            trimmed_items = items[:3] + [("...", "... trimmed ...")] + items[-3:]
            data["apps"] = dict(trimmed_items)
            data["_trimmed_count"] = len(items)

    return data

def test_get_dashboard(session, dashboard_id):
    test_name = f"test_get_dashboard_{dashboard_id}"
    try:
        response = session.get(f"{BASE_URL}/dash?dashboard_id={dashboard_id}", timeout=15)
        if response.status_code != 200:
            log_test_result(test_name, "fail", f"Failed with status {response.status_code}")
            return False

        data = response.json()
        
        # Handle Alfred dashboard differently
        if dashboard_id == "alfred":
            if not isinstance(data.get("user"), dict) or "conversations" not in data:
                log_test_result(test_name, "fail", "Invalid Alfred dashboard structure")
                return False
            # Trim conversations if there are many
            if len(data.get("conversations", [])) > 6:
                data["conversations"] = data["conversations"][:3] + [{"id": "...", "trimmed": True}] + data["conversations"][-3:]
                data["_trimmed_conversations_count"] = len(data["conversations"])
        else:
            if "apps" not in data:
                log_test_result(test_name, "fail", "Missing 'apps' in dashboard data")
                return False
            data = trim_dashboard_data(data)

        log_test_result(test_name, "pass", responses=[data])
        return True
    except Exception as e:
        log_test_result(test_name, "fail", str(e))
        return False

def test_refresh(session, dashboard_id):
    test_name = f"test_refresh_{dashboard_id}"
    try:
        response = session.get(f"{BASE_URL}/dash?action=refresh&dashboard_id={dashboard_id}", timeout=60)
        if response.status_code != 200:
            log_test_result(test_name, "fail", f"Failed with status {response.status_code}")
            return False

        data = response.json()
        if isinstance(data, dict):
            data = trim_dashboard_data(data)

        log_test_result(test_name, "pass", responses=[data])
        return True
    except Exception as e:
        log_test_result(test_name, "fail", str(e))
        return False

def test_chat_flow(session):
    test_name = "test_chat_flow"
    try:
        # Start new conversation on Alfred dashboard
        conversation = test_new_conversation(session)
        if not conversation:
            return False

        # Test file upload
        if not test_file_upload(session, conversation["id"], conversation["messages"]):
            return False

        # Test conversation on each dashboard
        for oracle in oracles:
            if not test_dashboard_conversation(session, oracle["dashboard_id"], conversation):
                return False

        # Test saving conversation
        if not test_save_conversation(session, conversation["id"], conversation["messages"]):
            return False

        # Test renaming conversation
        if not test_rename_conversation(session, conversation["id"]):
            return False

        # Test loading saved conversation
        if not test_load_conversation(session, conversation["id"]):
            return False

        # Test deleting conversation
        if not test_delete_conversation(session, conversation["id"]):
            return False

        log_test_result(test_name, "pass", "Complete chat flow successful")
        return True
    except Exception as e:
        log_test_result(test_name, "fail", str(e))
        return False

def test_new_conversation(session):
    try:
        response = session.post(f"{BASE_URL}/chat", json={
            "dashboard_id": "alfred",
            "prompt": f"Hi, I'm {TEST_USER['name']}",
            "messages": []
        })
        
        if response.status_code != 200:
            log_test_result("test_new_conversation", "fail", "Failed to create conversation")
            return None
            
        data = response.json()
        return {
            "id": data.get("conversation_id"),
            "messages": data.get("messages", [])
        }
    except Exception as e:
        log_test_result("test_new_conversation", "fail", str(e))
        return None
    
def test_rename_conversation(session, conversation_id):
    test_name = "test_rename_conversation"
    try:
        # Generate a unique test name just like the frontend does
        new_name = f"Test Conversation {datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Step 1: Send rename request exactly like handleNameUpdate does
        response = session.post(f"{BASE_URL}/chat", json={
            "action": "update_name",
            "conversation_id": conversation_id,
            "name": new_name,
            "dashboard_id": "alfred"
        })

        # Step 2: Check response matches what frontend expects
        if response.status_code != 200:
            log_test_result(test_name, "fail", 
                f"Failed to rename conversation: Status code {response.status_code} - {response.text}")
            return False

        resp_data = response.json()
        if resp_data.get("status") != "success" or resp_data.get("name") != new_name:
            log_test_result(test_name, "fail", 
                f"Invalid rename response: {resp_data}")
            return False

        log_test_result(test_name, "pass", f"Successfully renamed conversation to: {new_name}")
        return True

    except Exception as e:
        log_test_result(test_name, "fail", str(e))
        return False

def test_file_upload(session, conversation_id, messages):
    test_name = "test_file_upload"
    try:
        # Get upload URL
        response = session.post(f"{BASE_URL}/chat", json={
            "action": "get_upload_url",
            "dashboard_id": "alfred",
            "file_extension": ".txt",
            "conversation_id": conversation_id,
            "original_filename": "test_analysis.txt"
        })
        
        if response.status_code != 200:
            log_test_result(test_name, "fail", "Failed to get upload URL")
            return False

        upload_data = response.json()
        presigned_post = upload_data["presigned_post"]

        # Upload file
        with open(TEST_FILE_PATH, 'rb') as f:
            files = {'file': ('test_analysis.txt', f)}
            response = session.post(presigned_post["url"], 
                                  data=presigned_post["fields"],
                                  files=files)

        if response.status_code not in [200, 201, 204]:
            log_test_result(test_name, "fail", "Failed to upload file to S3")
            return False

        # Wait for processing
        time.sleep(5)

        log_test_result(test_name, "pass", "File upload successful")
        return True
    except Exception as e:
        log_test_result(test_name, "fail", str(e))
        return False

def test_dashboard_conversation(session, dashboard_id, conversation):
    test_name = f"test_conversation_{dashboard_id}"
    try:
        prompts = {
            "alfred": ["What dashboards are available?", "Can you analyze the uploaded file?"],
            "env_config": ["What environment information can you show me?"],
            "devision": ["What device information is available?"],
            "lucius": ["What security alerts are there?"]
        }

        for prompt in prompts.get(dashboard_id, []):
            response = session.post(f"{BASE_URL}/chat", json={
                "dashboard_id": dashboard_id,
                "prompt": prompt,
                "conversation_id": conversation["id"],
                "messages": conversation["messages"]
            })

            if response.status_code != 200:
                log_test_result(test_name, "fail", f"Failed with prompt: {prompt}")
                return False

            conversation["messages"] = response.json().get("messages", conversation["messages"])

        log_test_result(test_name, "pass")
        return True
    except Exception as e:
        log_test_result(test_name, "fail", str(e))
        return False

def test_save_conversation(session, conversation_id, messages):
    test_name = "test_save_conversation"
    try:
        response = session.post(f"{BASE_URL}/chat", json={
            "action": "save",
            "dashboard_id": "alfred",
            "conversation_id": conversation_id,
            "messages": messages
        })

        if response.status_code != 200:
            log_test_result(test_name, "fail", "Failed to save conversation")
            return False

        log_test_result(test_name, "pass")
        return True
    except Exception as e:
        log_test_result(test_name, "fail", str(e))
        return False

def test_load_conversation(session, conversation_id):
    test_name = "test_load_conversation"
    try:
        response = session.get(
            f"{BASE_URL}/chat?action=get_conversation&dashboard_id=alfred&conversation_id={conversation_id}"
        )

        if response.status_code != 200:
            log_test_result(test_name, "fail", "Failed to load conversation")
            return False

        data = response.json()
        if not data.get("messages", {}).get("messages"):
            log_test_result(test_name, "fail", "Loaded conversation has no messages")
            return False

        log_test_result(test_name, "pass")
        return True
    except Exception as e:
        log_test_result(test_name, "fail", str(e))
        return False

def test_delete_conversation(session, conversation_id):
    test_name = "test_delete_conversation"
    try:
        response = session.post(f"{BASE_URL}/chat", json={
            "action": "delete_conversation",
            "dashboard_id": "alfred",
            "conversation_id": conversation_id
        })

        if response.status_code != 200:
            log_test_result(test_name, "fail", "Failed to delete conversation")
            return False

        # Verify deletion by attempting to load the conversation
        verify_response = session.get(
            f"{BASE_URL}/chat?action=get_conversation&dashboard_id=alfred&conversation_id={conversation_id}"
        )
        
        if verify_response.status_code == 200:
            log_test_result(test_name, "fail", "Conversation still exists after deletion")
            return False

        log_test_result(test_name, "pass")
        return True
    except Exception as e:
        log_test_result(test_name, "fail", str(e))
        return False

def run_tests():
    logger.info("Starting test suite")
    time.sleep(20)  # Wait for server to start
    session = create_session()

    # Create test file
    with open(TEST_FILE_PATH, 'w') as f:
        f.write("This is a test file for upload and analysis.")

    try:
        # Test health check
        if not test_healthz(session):
            return

        # Test dashboards in parallel
        with ThreadPoolExecutor(max_workers=len(oracles)) as executor:
            futures = []
            for oracle in oracles:
                futures.append(
                    executor.submit(test_get_dashboard, session, oracle["dashboard_id"])
                )
                futures.append(
                    executor.submit(test_refresh, session, oracle["dashboard_id"])
                )
            
            # Wait for all operations to complete
            for future in as_completed(futures):
                future.result()

        # Test chat flow sequentially
        test_chat_flow(session)

    except Exception as e:
        logger.error(f"Test suite failed: {e}")
    finally:
        # Clean up test file
        if os.path.exists(TEST_FILE_PATH):
            os.remove(TEST_FILE_PATH)

        # Generate summary
        with open('log.json', 'w') as log_file:
            json.dump(test_results, log_file, indent=4)

        summary = f"""
            Test Summary:
            Total Tests: {test_results['summary']['pass_count'] + test_results['summary']['fail_count']}
            Pass: {test_results['summary']['pass_count']}
            Fail: {test_results['summary']['fail_count']}

            Failed Tests:
            {chr(10).join(f'- {detail["test_name"]}: {detail["message"]}' 
                for detail in test_results['details'] 
                if detail['status'] == 'fail')}
            """
        with open('summary.log', 'w') as summary_file:
            summary_file.write(summary)
        print(summary)

if __name__ == "__main__":
    run_tests()