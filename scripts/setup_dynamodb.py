from __future__ import annotations

import os
import sys
import time
import argparse
from pathlib import Path

import botocore
import boto3
from dotenv import load_dotenv, find_dotenv


def load_env() -> None:
    env_path = find_dotenv(usecwd=True)
    if not env_path:
        repo_root = Path(__file__).resolve().parents[1]
        candidate = repo_root / ".env"
        if candidate.exists():
            env_path = str(candidate)

    if env_path:
        load_dotenv(env_path, override=False)


def get_session(profile: str | None, region: str | None) -> boto3.session.Session:
    if profile:
        return boto3.session.Session(profile_name=profile, region_name=region)
    return boto3.session.Session(region_name=region)


def ensure_table(session: boto3.session.Session, region: str, endpoint: str | None,
                 table_name: str, billing_mode: str,
                 read_capacity: int, write_capacity: int) -> None:
    ddb = session.resource("dynamodb", region_name=region, endpoint_url=endpoint or None)
    client = session.client("dynamodb", region_name=region, endpoint_url=endpoint or None)

    table = ddb.Table(table_name)
    try:
        table.load()  # describe
        print(f"[OK] Table '{table_name}' already exists. Status: {table.table_status}")
    except botocore.exceptions.ClientError as e:
        if e.response.get("Error", {}).get("Code") != "ResourceNotFoundException":
            raise
        print(f"[..] Creating table '{table_name}' ...")
        kwargs = {
            "TableName": table_name,
            "AttributeDefinitions": [{"AttributeName": "email", "AttributeType": "S"}],
            "KeySchema": [{"AttributeName": "email", "KeyType": "HASH"}],
        }
        if billing_mode.upper() == "PAY_PER_REQUEST":
            kwargs["BillingMode"] = "PAY_PER_REQUEST"
        else:
            kwargs["ProvisionedThroughput"] = {
                "ReadCapacityUnits": read_capacity,
                "WriteCapacityUnits": write_capacity,
            }

        client.create_table(**kwargs)
        waiter = client.get_waiter("table_exists")
        waiter.wait(TableName=table_name)
        time.sleep(1)  # small buffer
        print(f"[OK] Table '{table_name}' created and active.")


def ensure_ttl(session: boto3.session.Session, region: str, endpoint: str | None,
               table_name: str, ttl_attr: str = "ttl") -> None:
    client = session.client("dynamodb", region_name=region, endpoint_url=endpoint or None)

    try:
        desc = client.describe_time_to_live(TableName=table_name)
        status = desc.get("TimeToLiveDescription", {}).get("TimeToLiveStatus", "DISABLED")
    except botocore.exceptions.ClientError as e:
        print(f"[WARN] describe_time_to_live failed: {e}")
        status = "UNKNOWN"

    if status == "ENABLED":
        print(f"[OK] TTL already ENABLED on '{table_name}' (attribute '{ttl_attr}').")
        return

    print(f"[..] Enabling TTL on '{table_name}' using attribute '{ttl_attr}' ...")
    try:
        client.update_time_to_live(
            TableName=table_name,
            TimeToLiveSpecification={"Enabled": True, "AttributeName": ttl_attr},
        )
        print("[OK] TTL update submitted (status will become ENABLED shortly).")
    except botocore.exceptions.ClientError as e:
        print(f"[ERROR] Failed to enable TTL: {e}")
        if os.getenv("CI"):
            raise


def main():
    load_env()

    parser = argparse.ArgumentParser(description="Create DynamoDB table and enable TTL (env-aware).")
    parser.add_argument("--table-name", default=os.getenv("OTP_TABLE_NAME", "AuthOtp"))
    parser.add_argument("--region", default=os.getenv("AWS_REGION", "ap-south-1"))
    parser.add_argument("--endpoint-url", default=os.getenv("DYNAMODB_ENDPOINT"))
    parser.add_argument("--profile", default=os.getenv("AWS_PROFILE"))
    parser.add_argument("--billing-mode", choices=["PAY_PER_REQUEST", "PROVISIONED"], default=os.getenv("DDB_BILLING_MODE", "PAY_PER_REQUEST"))
    parser.add_argument("--read-capacity", type=int, default=int(os.getenv("DDB_READ_CAPACITY", "5")))
    parser.add_argument("--write-capacity", type=int, default=int(os.getenv("DDB_WRITE_CAPACITY", "5")))
    parser.add_argument("--ttl-attr", default=os.getenv("DDB_TTL_ATTR", "ttl"))
    args = parser.parse_args()

    # Helpful echo (no secrets)
    print(f"[CFG] table={args.table_name} region={args.region} endpoint={args.endpoint_url or '-'} "
          f"profile={args.profile or '-'} billing={args.billing_mode} "
          f"rcu={args.read_capacity} wcu={args.write_capacity} ttl_attr={args.ttl_attr}")

    session = get_session(args.profile, args.region)

    try:
        ensure_table(
            session=session,
            region=args.region,
            endpoint=args.endpoint_url,
            table_name=args.table_name,
            billing_mode=args.billing_mode,
            read_capacity=args.read_capacity,
            write_capacity=args.write_capacity,
        )
        ensure_ttl(
            session=session,
            region=args.region,
            endpoint=args.endpoint_url,
            table_name=args.table_name,
            ttl_attr=args.ttl_attr,
        )
        print("[DONE] DynamoDB setup complete.")
    except Exception as exc:
        print(f"[FAIL] {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
