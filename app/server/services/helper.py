import json
import logging
import os
import time
import uuid

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def get_or_throw(key):
    value = os.getenv(key)
    if value is None:
        raise ValueError(f"Environment variable {key} is not set")
    return value

class AWSClient:
    def __init__(self, service_name):
        environment = os.getenv("ENVIRONMENT", "production")
        if environment == "local":
            self.client = boto3.client(
                service_name,
                endpoint_url="http://localstack:4566",
                aws_access_key_id="test",
                aws_secret_access_key="test",
                region_name="us-east-1",
            )
        elif environment == "development":
            session = boto3.Session(profile_name=os.getenv("AWS_PROFILE"))
            self.client = session.client(service_name)
        else:
            self.client = boto3.client(service_name, region_name=os.getenv("AWS_REGION"))


class S3Service:
    def __init__(self):
        self.client = boto3.client("s3", region_name=os.getenv("AWS_REGION"))

    def list_objects_v2(self, **kwargs):
        """List objects in S3 bucket with v2 API."""
        try:
            return self.client.list_objects_v2(**kwargs)
        except Exception as e:
            logger.error(f"Error listing objects: {e}")
            return {'Contents': []}
        
    def delete_object(self, bucket, key):
        """Delete an object from S3."""
        try:
            self.client.delete_object(Bucket=bucket, Key=key)
            logger.info(f"Deleted object {bucket}/{key}")
            return True
        except self.client.exceptions.NoSuchKey:
            logger.warning(f"Object {bucket}/{key} not found.")
            return False
        except Exception as e:
            logger.error(f"Error deleting object {bucket}/{key}: {e}")
            return False

    def head_object(self, bucket, key):
        """Check if an object exists and get its metadata."""
        try:
            return self.client.head_object(Bucket=bucket, Key=key)
        except self.client.exceptions.ClientError as e:
            if e.response['Error']['Code'] == '404':
                return None
            raise

    def get_json(self, bucket, key, max_retries=12, retry_delay=5):
        """Get and parse JSON object from S3."""
        for attempt in range(max_retries):
            try:
                obj = self.client.get_object(Bucket=bucket, Key=key)
                content = obj["Body"].read()
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    logger.warning(
                        f"File {key} is not valid JSON. Returning raw content."
                    )
                    return {"raw_content": content.decode("utf-8")}
            except self.client.exceptions.NoSuchKey:
                if attempt < max_retries - 1:
                    logger.info(
                        f"File {key} not found. Retrying in {retry_delay} seconds..."
                    )
                    time.sleep(retry_delay)
                else:
                    logger.error(f"File {key} not found after {max_retries} attempts.")
                    return {"error": "File not found"}
            except Exception as e:
                logger.error(f"Error fetching {key} from S3: {e}")
                return {"error": str(e)}

    def upload_json(self, bucket, key, data):
        """Upload JSON data to S3."""
        try:
            self.client.put_object(
                Bucket=bucket,
                Key=key,
                Body=json.dumps(data).encode("utf-8"),
                ContentType="application/json",
            )
            logger.info(f"Uploaded JSON data to {bucket}/{key}")
            return True
        except Exception as e:
            logger.error(f"Error uploading JSON data to {bucket}/{key}: {e}")
            return False

    def get_object_tags(self, bucket, key):
        """Get tags for an S3 object."""
        try:
            response = self.client.get_object_tagging(
                Bucket=bucket,
                Key=key
            )
            # Convert tag values to strings to ensure compatibility
            return {tag['Key']: str(tag['Value']) for tag in response.get('TagSet', [])}
        except self.client.exceptions.NoSuchKey:
            logger.warning(f"Object {bucket}/{key} not found when getting tags")
            return {}
        except Exception as e:
            logger.error(f"Error getting tags for {bucket}/{key}: {e}")
            return {}

    def put_object_tags(self, bucket, key, tags):
        """Put tags on an S3 object."""
        try:
            # Ensure all tag values are strings
            tag_set = [{'Key': k, 'Value': str(v)} for k, v in tags.items()]
            self.client.put_object_tagging(
                Bucket=bucket,
                Key=key,
                Tagging={
                    'TagSet': tag_set
                }
            )
            logger.info(f"Successfully updated tags for {bucket}/{key}")
            return True
        except self.client.exceptions.NoSuchKey:
            logger.error(f"Object {bucket}/{key} not found when putting tags")
            return False
        except Exception as e:
            logger.error(f"Error putting tags on {bucket}/{key}: {e}")
            return False

    def list_conversations(self, bucket, prefix):
        """List all conversations for a user with improved tag handling."""
        try:
            paginator = self.client.get_paginator('list_objects_v2')
            page_iterator = paginator.paginate(Bucket=bucket, Prefix=prefix)
            
            conversations = {}
            for page in page_iterator:
                for obj in page.get('Contents', []):
                    key = obj['Key']
                    parts = key.split('/')
                    if len(parts) < 2:
                        continue
                    
                    conversation_id = parts[1]
                    
                    # Only process if we haven't seen this conversation or if this is messages.json
                    if conversation_id not in conversations or key.endswith('messages.json'):
                        # Initialize or update conversation entry
                        if conversation_id not in conversations:
                            conversations[conversation_id] = {
                                'conversation_id': conversation_id,
                                'name': conversation_id,  # Default name
                                'uploads': [],
                                'last_modified': obj['LastModified'].isoformat()
                            }
                        
                        # If this is messages.json, get the name from tags
                        if key.endswith('messages.json'):
                            tags = self.get_object_tags(bucket, key)
                            if 'name' in tags:
                                conversations[conversation_id]['name'] = tags['name']
                    
                    # Handle uploads
                    if 'uploads/' in key:
                        try:
                            tags = self.get_object_tags(bucket, key)
                            original_filename = tags.get('original-filename') or key.split('/')[-1]
                            
                            conversations[conversation_id]['uploads'].append({
                                'key': key,
                                'original_filename': original_filename,
                                'last_modified': obj['LastModified'].isoformat(),
                                'size': obj['Size']
                            })
                        except Exception as e:
                            logger.error(f"Error processing upload {key}: {e}")

            return list(conversations.values())
        except Exception as e:
            logger.error(f"Error listing conversations: {e}")
            return []

    def generate_presigned_url(
        self,
        bucket,
        key,
        username,
        conversation_id,
        file_extension,
        original_filename,
        expiration=3600,
    ):
        """Generate a presigned URL for file upload."""
        try:
            content_type = self.get_content_type(file_extension)

            fields = {
                "Content-Type": content_type,
                "tagging": f"<Tagging><TagSet><Tag><Key>username</Key><Value>{username}</Value></Tag><Tag><Key>conversation_id</Key><Value>{conversation_id}</Value></Tag></TagSet></Tagging>",
                "x-amz-meta-original-filename": original_filename,
            }
            conditions = [
                {
                    "tagging": f"<Tagging><TagSet><Tag><Key>username</Key><Value>{username}</Value></Tag><Tag><Key>conversation_id</Key><Value>{conversation_id}</Value></Tag></TagSet></Tagging>"
                },
                ["starts-with", "$Content-Type", content_type],
                {"x-amz-meta-original-filename": original_filename},
            ]

            presigned_post = self.client.generate_presigned_post(
                Bucket=bucket,
                Key=key,
                Fields=fields,
                Conditions=conditions,
                ExpiresIn=expiration,
            )

            logger.info(f"Generated presigned POST data for {bucket}/{key}")
            return presigned_post
        except Exception as e:
            logger.error(f"Error generating presigned POST data: {e}")
            return None

    @staticmethod
    def get_content_type(file_extension):
        """Get the content type for a file extension."""
        content_types = {
            "txt": "text/plain",
            "pdf": "application/pdf",
            "doc": "application/msword",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "csv": "text/csv",
            "json": "application/json",
        }
        return content_types.get(file_extension.lower(), "application/octet-stream")

class LambdaService(AWSClient):
    def __init__(self):
        super().__init__("lambda")

    def invoke_function(self, function_name, payload):
        try:
            response = self.client.invoke(
                FunctionName=function_name,
                InvocationType="RequestResponse",
                Payload=json.dumps(payload),
            )
            return json.loads(response["Payload"].read())
        except self.client.exceptions.ResourceNotFoundException:
            logger.error(f"Lambda function not found: {function_name}")
            return {"error": f"Lambda function not found: {function_name}"}
        except Exception as e:
            logger.error(f"Error invoking Lambda function: {e}")
            return {"error": str(e)}
