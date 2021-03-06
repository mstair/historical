"""
.. module: historical.tests.test_security_group
    :platform: Unix
    :copyright: (c) 2017 by Netflix Inc., see AUTHORS for more
    :license: Apache, see LICENSE for more details.
.. author:: Kevin Glisson <kglisson@netflix.com>
"""
import json
import os
import time
from datetime import datetime

import boto3

from historical.common.sqs import get_queue_url
from historical.tests.factories import (
    CloudwatchEventFactory,
    DetailFactory,
    RecordsFactory,
    DynamoDBDataFactory,
    DynamoDBRecordFactory,
    UserIdentityFactory,
    serialize,
    SQSDataFactory, SnsDataFactory)

SECURITY_GROUP = {
    'arn': 'arn:aws:ec2:us-east-1:123456789012:security-group/sg-1234568',
    'GroupId': 'sg-1234568',
    'GroupName': 'testGroup',
    'eventSource': 'aws.ec2',
    'VpcId': 'vpc-123343',
    'accountId': '123456789012',
    'OwnerId': '123456789012',
    'Description': 'This is a test',
    'Region': 'us-east-1',
    'Tags': [{'Name': 'test', 'Value': '<empty>'}],
    'configuration': {
        'Description': 'string',
        'GroupName': 'string',
        'IpPermissions': [
            {
                'FromPort': 123,
                'IpProtocol': 'string',
                'IpRanges': [
                    {
                        'CidrIp': 'string'
                    },
                ],
                'Ipv6Ranges': [
                    {
                        'CidrIpv6': 'string'
                    },
                ],
                'PrefixListIds': [
                    {
                        'PrefixListId': 'string'
                    },
                ],
                'ToPort': 123,
                'UserIdGroupPairs': [
                    {
                        'GroupId': 'string',
                        'GroupName': 'string',
                        'PeeringStatus': 'string',
                        'UserId': 'string',
                        'VpcId': 'string',
                        'VpcPeeringConnectionId': 'string'
                    },
                ]
            },
        ],
        'OwnerId': 'string',
        'GroupId': 'string',
        'IpPermissionsEgress': [
            {
                'FromPort': 123,
                'IpProtocol': 'string',
                'IpRanges': [
                    {
                        'CidrIp': 'string'
                    },
                ],
                'Ipv6Ranges': [
                    {
                        'CidrIpv6': 'string'
                    },
                ],
                'PrefixListIds': [
                    {
                        'PrefixListId': 'string'
                    },
                ],
                'ToPort': 123,
                'UserIdGroupPairs': [
                    {
                        'GroupId': 'string',
                        'GroupName': 'string',
                        'PeeringStatus': 'string',
                        'UserId': 'string',
                        'VpcId': 'string',
                        'VpcPeeringConnectionId': 'string'
                    },
                ]
            },
        ],
        'Tags': [
            {
                'Key': 'string',
                'Value': 'string'
            },
        ],
        'VpcId': 'string'
    }
}


def test_current_table(current_security_group_table):
    from historical.security_group.models import CurrentSecurityGroupModel

    CurrentSecurityGroupModel(**SECURITY_GROUP).save()

    items = list(CurrentSecurityGroupModel.query('arn:aws:ec2:us-east-1:123456789012:security-group/sg-1234568'))

    assert len(items) == 1
    assert isinstance(items[0].ttl, int)
    assert items[0].ttl > 0


def test_durable_table(durable_security_group_table):
    from historical.security_group.models import DurableSecurityGroupModel

    # we are explicit about our eventTimes because as RANGE_KEY it will need to be unique.
    sg = SECURITY_GROUP.copy()
    sg['eventTime'] = datetime(2017, 5, 11, 23, 30)
    sg.pop("eventSource")
    DurableSecurityGroupModel(**sg).save()

    items = list(DurableSecurityGroupModel.query('arn:aws:ec2:us-east-1:123456789012:security-group/sg-1234568'))

    assert len(items) == 1
    assert not getattr(items[0], "ttl", None)

    sg['eventTime'] = datetime(2017, 5, 12, 23, 30)
    DurableSecurityGroupModel(**sg).save()

    items = list(DurableSecurityGroupModel.query('arn:aws:ec2:us-east-1:123456789012:security-group/sg-1234568'))

    assert len(items) == 2


def test_poller(historical_sqs, historical_role, mock_lambda_environment, security_groups, swag_accounts):
    from historical.security_group.poller import handler
    handler(None, None)

    # Need to ensure that 3 total SGs were added into SQS:
    sqs = boto3.client("sqs", region_name="us-east-1")
    queue_url = get_queue_url(os.environ['POLLER_QUEUE_NAME'])

    messages = sqs.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=10)['Messages']
    assert len(messages) == 3


def test_differ(current_security_group_table, durable_security_group_table, mock_lambda_environment):
    from historical.security_group.models import DurableSecurityGroupModel
    from historical.security_group.differ import handler
    from historical.models import TTL_EXPIRY

    ttl = int(time.time() + TTL_EXPIRY)
    new_group = SECURITY_GROUP.copy()
    new_group.pop("eventSource")
    new_group['eventTime'] = datetime(year=2017, month=5, day=12, hour=10, minute=30, second=0).isoformat() + 'Z'
    new_group["ttl"] = ttl
    data = json.dumps(DynamoDBRecordFactory(dynamodb=DynamoDBDataFactory(
        NewImage=new_group,
        Keys={
            'arn': new_group['arn']
        }
    ), eventName='INSERT'), default=serialize)
    data = RecordsFactory(records=[SQSDataFactory(body=json.dumps(SnsDataFactory(Message=data), default=serialize))])
    data = json.loads(json.dumps(data, default=serialize))
    handler(data, None)
    assert DurableSecurityGroupModel.count() == 1

    # ensure no new record for the same data
    duplicate_group = SECURITY_GROUP.copy()
    duplicate_group.pop("eventSource")
    duplicate_group['eventTime'] = datetime(year=2017, month=5, day=12, hour=11, minute=30, second=0).isoformat() + 'Z'
    duplicate_group["ttl"] = ttl
    data = json.dumps(DynamoDBRecordFactory(dynamodb=DynamoDBDataFactory(
        NewImage=duplicate_group,
        Keys={
            'arn': duplicate_group['arn']
        }
    ), eventName='MODIFY'), default=serialize)
    data = RecordsFactory(records=[SQSDataFactory(body=json.dumps(SnsDataFactory(Message=data), default=serialize))])
    data = json.loads(json.dumps(data, default=serialize))
    handler(data, None)
    assert DurableSecurityGroupModel.count() == 1

    updated_group = SECURITY_GROUP.copy()
    updated_group.pop("eventSource")
    updated_group['eventTime'] = datetime(year=2017, month=5, day=12, hour=11, minute=30, second=0).isoformat() + 'Z'
    updated_group['configuration']['Description'] = 'changeme'
    updated_group["ttl"] = ttl
    data = json.dumps(DynamoDBRecordFactory(dynamodb=DynamoDBDataFactory(
        NewImage=updated_group,
        Keys={
            'arn': SECURITY_GROUP['arn']
        }
    ), eventName='MODIFY'), default=serialize)
    data = RecordsFactory(records=[SQSDataFactory(body=json.dumps(SnsDataFactory(Message=data), default=serialize))])
    data = json.loads(json.dumps(data, default=serialize))
    handler(data, None)
    assert DurableSecurityGroupModel.count() == 2

    updated_group = SECURITY_GROUP.copy()
    updated_group.pop("eventSource")
    updated_group['eventTime'] = datetime(year=2017, month=5, day=12, hour=9, minute=30, second=0).isoformat() + 'Z'
    updated_group['configuration']['IpPermissions'][0]['IpRanges'][0]['CidrIp'] = 'changeme'
    updated_group["ttl"] = ttl
    data = json.dumps(DynamoDBRecordFactory(dynamodb=DynamoDBDataFactory(
        NewImage=updated_group,
        Keys={
            'arn': SECURITY_GROUP['arn']
        }
    ), eventName='MODIFY'), default=serialize)
    data = RecordsFactory(records=[SQSDataFactory(body=json.dumps(SnsDataFactory(Message=data), default=serialize))])
    data = json.loads(json.dumps(data, default=serialize))
    handler(data, None)
    assert DurableSecurityGroupModel.count() == 3

    deleted_group = SECURITY_GROUP.copy()
    deleted_group.pop("eventSource")
    deleted_group['eventTime'] = datetime(year=2017, month=5, day=12, hour=12, minute=30, second=0).isoformat() + 'Z'
    deleted_group["ttl"] = ttl

    # ensure new record
    data = json.dumps(DynamoDBRecordFactory(dynamodb=DynamoDBDataFactory(
        OldImage=deleted_group,
        Keys={
            'arn': SECURITY_GROUP['arn']
        }),
        eventName='REMOVE',
        userIdentity=UserIdentityFactory(
                type='Service',
                principalId='dynamodb.amazonaws.com'
        )), default=serialize)
    data = RecordsFactory(records=[SQSDataFactory(body=json.dumps(SnsDataFactory(Message=data), default=serialize))])
    data = json.loads(json.dumps(data, default=serialize))
    handler(data, None)
    assert DurableSecurityGroupModel.count() == 4


def test_collector(historical_role, mock_lambda_environment, historical_sqs, security_groups,
                   current_security_group_table):
    from historical.security_group.models import CurrentSecurityGroupModel
    from historical.security_group.collector import handler
    event = CloudwatchEventFactory(
        detail=DetailFactory(
            requestParameters={'groupId': security_groups['GroupId']},
            eventName='CreateSecurityGroup'
        ),
    )
    data = json.dumps(event, default=serialize)
    data = RecordsFactory(records=[SQSDataFactory(body=data)])
    data = json.dumps(data, default=serialize)
    data = json.loads(data)

    handler(data, None)

    assert CurrentSecurityGroupModel.count() == 1

    event = CloudwatchEventFactory(
        detail=DetailFactory(
            requestParameters={'groupId': security_groups['GroupId']},
            eventName='DeleteSecurityGroup'
        ),
    )
    data = json.dumps(event, default=serialize)
    data = RecordsFactory(records=[SQSDataFactory(body=data)])
    data = json.dumps(data, default=serialize)
    data = json.loads(data)

    handler(data, None)

    assert CurrentSecurityGroupModel.count() == 0
