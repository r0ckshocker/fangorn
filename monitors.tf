locals {
  monitor_options = {
    evaluation_window   = 300
    keep_alive         = 3600
    max_signal_duration = 86400
    detection_method    = "threshold"
  }

  # Network monitors
  network_monitors = {
    api_abuse = {
      name    = "api_abuse_detection"
      type    = "log_detection"
      enabled = true
      queries = [{
        query           = "@service:tempo @http.status_code:(429 OR 503)"
        name           = "api_abuse_attempts"
        aggregation    = "count"
        group_by_fields = ["network.client.geoip.ipAddress", "user.email"]
      }]
      cases = [{
        name          = "API Abuse Detected"
        status        = "medium"
        condition     = "api_abuse_attempts > 50"
        notifications = []
      }]
      options = local.monitor_options
      tags    = ["attack:dos"]
    },

    llm_abuse = {
      name    = "llm_abuse_detection"
      type    = "log_detection"
      enabled = true
      queries = [{
        query           = "@service:tempo @http.url_details.path:\"/v1/ai/chats\" @http.status_code:200"
        name           = "llm_usage"
        aggregation    = "count"
        group_by_fields = ["user.email"]
      }]
      cases = [{
        name          = "Excessive LLM Usage Detected"
        status        = "medium"
        condition     = "llm_usage > 200"
        notifications = []
      }]
      options = local.monitor_options
      tags    = ["attack:resource_abuse", "service:llm"]
    },

    cloud_recon = {
      name    = "cloud_recon_detection"
      type    = "log_detection"
      enabled = true
      queries = [{
        query           = <<-EOQ
          @service:tempo
          @http.url_details.path:(
            "/.aws/credentials" OR 
            "/docker-compose.yml" OR 
            "/.env" OR 
            "/config" OR
            "/.git" OR
            "/swagger" OR
            "/actuator"
          )
        EOQ
        name           = "cloud_recon_attempts"
        aggregation    = "count"
        group_by_fields = ["network.client.geoip.ipAddress", "http.url_details.path"]
      }]
      cases = [{
        name          = "Cloud Reconnaissance Detected"
        status        = "high"
        condition     = "cloud_recon_attempts > 5"
        notifications = []
      }]
      options = local.monitor_options
      tags    = ["attack:reconnaissance"] 
    }
  }

  # Auth Monitors
  auth_monitors = {
    auth_anomalies = {
      name    = "authentication_anomalies_detection"
      type    = "log_detection"
      enabled = true
      queries = [{
        query           = "@http.status_code:401 @http.url_details.path:(\"/v1/login\" OR \"/v1/login/sso\") @service:tempo"
        name           = "auth_failures"
        aggregation    = "count"
        group_by_fields = ["network.client.geoip.ipAddress", "user.email"]
      }]
      cases = [{
        name          = "Authentication Anomalies Detected"
        status        = "high"
        condition     = "auth_failures > 25"
        notifications = []
      }]
      options = local.monitor_options
      tags    = ["attack:credential_access"]
    },

    impossible_travel = {
      name    = "impossible_travel_detection"
      enabled = true
      queries = [{
        query           = "service:tempo status:200 log.attributes.user.session_id_client_trace log.attributes.user.geoip"
        name           = "impossible_travel"
        aggregation    = "count"
        group_by_fields = [
        "log.attributes.user.session_id_client_trace",
        "log.attributes.user.geoip.country.name",
        "log.attributes.user.geoip.city.name"
        ]
      }]
      cases = [{
        name          = "Impossible Travel Detected"
        status        = "high"
        condition     = "impossible_travel > 0"
        notifications = []
      }]
      options = local.monitor_options
      tags    = ["environment:production"]
    },

    session_anomalies = {
      name    = "session_anomalies_detection"
      enabled = true
      queries = [{
        query           = "service:tempo status:200 @network.client.geoip.ipAddress:* @user.session_id:*"
        name           = "session_anomalies"
        aggregation    = "count"
        group_by_fields = [
        "log.attributes.network.client.geoip.ipAddress",
        "log.attributes.user.session_id_client_trace"
        ]
      }]
      cases = [{
        name          = "Suspicious Session Activity Detected"
        status        = "critical"
        condition     = "session_anomalies > 5"
        notifications = []
      }]
      options = local.monitor_options
      tags    = ["attack:session_hijacking"]
    }
  }

  # Data Monitors
  data_monitors = {
    data_exfiltration = {
      name    = "data_exfiltration_detection"
      enabled = true
      queries = [{
        name           = "data_exfiltration_attempts"
        aggregation    = "count"
        query = "service:tempo http.url_details.path:(\"/v1/procedures/download\" OR \"/v1/batch/containers/download\" OR \"/v1/batch/instances/download\" OR \"/v1/equipment/download\") status:200"
        group_by_fields = ["network.client.geoip.ipAddress", "http.url_details.path"]
    }]
      cases = [{
        name          = "Data Exfiltration Detected"
        status        = "critical"
        condition     = "data_exfiltration_attempts > 15"
        notifications = []
      }]
      options = local.monitor_options
      tags    = ["attack:data_exfiltration", "type:security"]
    },

    mass_enumeration = {
      name    = "mass_enumeration_detection"
      enabled = true
      queries = [{
        query           = "service:tempo http.url_details.path:(\"/v1/users/min\" OR \"/v1/users/paginated\" OR \"/v1/procedures/query\" OR \"/v1/procedures/runnable\") status:200"
        name           = "mass_enumeration_attempts"
        aggregation    = "count"
        group_by_fields = []
      }]
      cases = [{
        name          = "Mass Enumeration Detected"
        status        = "high"
        condition     = "mass_enumeration_attempts > 100"
        notifications = local.notifications.enumeration
      }]
      options = local.monitor_options
      tags    = ["attack:enumeration", "environment:production"]
    }
  }

  # Privilege Monitors
  privilege_monitors = {
    privilege_escalation = {
      name    = "Privilege Escalation Access Attempt Detection"
      enabled = true
      queries = [{
        query           = "service:tempo status:403 (http.url_details.path:\"/apprentice/organization/configuration\" OR http.url_details.path:\"/apprentice/organization/devices/list\" OR http.url_details.path:\"/apprentice/organization/users/list\")"
        name           = "privilege_escalation_attempts"
        aggregation    = "count"
        group_by_fields = []
      }]
      cases = [{
        name          = "Privilege Escalation Attempt Detected"
        status        = "medium"
        condition     = "privilege_escalation_attempts > 5"
        notifications = local.notifications.privilege_escalation
      }]
      options = local.monitor_options
      tags    = ["environment:production"]
    }
  }

  # Security Monitors
  security_monitors = {
    critical_endpoint_exploitation = {
      name    = "critical_endpoint_exploitation_detection"
      enabled = true
      queries = [{
        query           = "@http.status_code:(401 OR 403 OR 404 OR 500) @http.url_details.route_ui:(\"/apprentice/organization/configuration\" OR \"/apprentice/organization/integrations/list\" OR \"/apprentice/organization/users/list\" OR \"/apprentice/organization/groups/list\" OR \"/apprentice/admin/organizations\") @http.url_details.path:(\"/v1/publish/teams\" OR \"/v1/multiverse/organizations/hierarchy-list\")"
        name           = "critical_endpoint_access_attempts"
        aggregation    = "count"
        group_by_fields = []
      }]
      cases = [{
        name          = "Critical Endpoint Exploitation Detected"
        status        = "medium"
        condition     = "critical_endpoint_access_attempts > 1"
        notifications = []
      }]
      options = local.monitor_options
      tags    = ["service:web", "attack:credential_access"]
    },

    critical_file_probing = {
      name    = "critical_file_and_admin_access_probing_detection"
      enabled = true
      queries = [{
        query           = "@http.url_details.path:(\"/.aws/credentials\" OR \"/docker-compose.yml\" OR \"/azure_credentials.json\" OR \"/.env.production\" OR \"/wordlist.txt\" OR \"/.ssh/id_rsa\" OR \"/.ssh/id_ed25519\" OR \"/.ssh/id_ecdsa\" OR \"/user_secrets.yml\" OR \"/secrets.json\" OR \"/etc/ssl/private/server.key\" OR \"/etc/shadow\" OR \"/v1;/manage;/env\" OR \"/v1;/actuators;/env\" OR \"/v1;/actuator;/env\" OR \"/v1;/system;/env\" OR \"/api;/internal;/actuator/env\" OR \"/api;/internal;/;env\" OR \"/api;/v1/manage;/env\" OR \"/api;/manage/;env\" OR \"/api;/v1;/system;/env\" OR \"/api;/system;/env\") -source:cloudflare"
        name           = "admin_and_critical_file_probing_activity"
        aggregation    = "count"
        group_by_fields = []
      }]
      cases = [{
        name          = "Sensitive File or Admin Probing Detected"
        status        = "medium"
        condition     = "admin_and_critical_file_probing_activity > 1"
        notifications = []
      }]
      options = local.monitor_options
      tags    = ["service:web", "attack:reconnaissance"]
    },

    excessive_login_errors = {
      name    = "excessive_login_errors_detection"
      enabled = true
      queries = [{
        query           = "@http.status_code:401 @http.url_details.path:\"/v1/login\""
        name           = "excessive_login_errors"
        aggregation    = "count"
        group_by_fields = []
      }]
      cases = [{
        name          = "Excessive Login Errors Detected"
        status        = "medium"
        condition     = "excessive_login_errors > 25"
        notifications = []
      }]
      options = local.monitor_options
      tags    = ["service:web", "attack:credential_access"]
    },

    failed_sso_login = {
      name    = "failed_sso_login_attempts_detection"
      enabled = true
      queries = [{
        query           = "@service:sso @logContext.method:unauthorized @http.status_code:401 @http.url_details.path:\"/v1/login/sso\""
        name           = "failed_sso_login_attempts"
        aggregation    = "count"
        group_by_fields = []
      }]
      cases = [{
        name          = "Failed SSO Login Attempts Detected"
        status        = "medium"
        condition     = "failed_sso_login_attempts > 11"
        notifications = []
      }]
      options = local.monitor_options
      tags    = ["service:web", "attack:credential_access"]
    },

    lateral_movement = {
      name    = "lateral_movement_detection"
      enabled = true
      queries = [{
        query           = "@network.client.geoip.ipAddress:* @dd.env:* @http.status_code:200"
        name           = "distinct_user_emails_per_ip"
        aggregation    = "count"
        group_by_fields = ["network.client.geoip.ipAddress", "dd.env"]
      }]
      cases = [{
        name          = "Lateral Movement Detected"
        status        = "medium"
        condition     = "distinct_user_emails_per_ip > 2"
        notifications = []
      }]
      options = {
        evaluation_window   = 600
        keep_alive         = 3600
        max_signal_duration = 86400
        detection_method    = "threshold"
      }
      tags    = ["service:web", "attack:lateral_movement"]
    },

    non_apprentice_admin = {
      name    = "non_apprentice_admin_endpoint_access"
      enabled = true
      queries = [{
        query           = "-@user.email:*apprenticefs.com -@user.email:*apprentice.io @user.email:* @http.url_details.path:\"/v1/multiverse/organizations/hierarchy-list\" @http.status_code:200"
        name           = "unauthorized_successful_access"
        aggregation    = "count"
        group_by_fields = []
      }]
      cases = [{
        name          = "Non-Apprentice Admin Endpoint Access Detected"
        status        = "critical"
        condition     = "unauthorized_successful_access > 1"
        notifications = []
      }]
      options = local.monitor_options
      tags    = ["service:web", "attack:credential_access"]
    }
  }
}