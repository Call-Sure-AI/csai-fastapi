import os
import boto3
from functools import lru_cache

class DynamoClient:
    def __init__(self):
        self.region = os.getenv("AWS_REGION", "ap-south-1")
        self.endpoint_url = os.getenv("DYNAMODB_ENDPOINT")
        profile = os.getenv("AWS_PROFILE")

        if profile:
            session = boto3.session.Session(profile_name=profile, region_name=self.region)
        else:
            session = boto3.session.Session(region_name=self.region)

        self._resource = session.resource(
            "dynamodb",
            endpoint_url=self.endpoint_url or None,
        )

    @lru_cache(maxsize=4)
    def get_table(self, table_name: str):
        return self._resource.Table(table_name)

dynamo_client = DynamoClient()
