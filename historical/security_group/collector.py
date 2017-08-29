"""
.. module: historical.security_group.collector
    :platform: Unix
    :copyright: (c) 2017 by Netflix Inc., see AUTHORS for more
    :license: Apache, see LICENSE for more details.
.. author:: Kevin Glisson <kglisson@netflix.com>
"""
import logging

from cloudaux.aws.ec2 import describe_security_groups
from historical.security_group.models import CurrentSecurityGroupModel

logging.basicConfig()
log = logging.getLogger('historical')
log.setLevel(logging.INFO)


def get_configuration_data(data):
    """Describes the current state of the object."""
    return describe_security_groups(**data)


def handler(event, context):
    """
    Historical security group event collector.

    This collector is responsible for processing Cloudwatch events and polling events.

    Polling Events
    When a polling event is received, this function is responsible for persisting
    configuration data to the correct DynamoDB tables.

    Cloudwatch Events
    When a Cloudwatch event is received, this function must first fetch configuration
    data from AWS before persisting data.
    """
    data = event
    log.debug('Successfully processed event. Data: {data}'.format(data=data))

    current_revision = CurrentSecurityGroupModel(**data)
    current_revision.save()
    log.debug('Successfully updated current Historical table')
