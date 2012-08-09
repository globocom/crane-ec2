import logging

import boto

from boto.ec2.regioninfo import RegionInfo
from boto.exception import EC2ResponseError
from django.conf import settings


class Client(object):

    def __init__(self):
        self._ec2_conn = None

    @property
    def ec2_conn(self):
        if not self._ec2_conn:
            self._ec2_conn = boto.connect_ec2(
                aws_access_key_id=settings.EC2_ACCESS_KEY,
                aws_secret_access_key=settings.EC2_SECRET_KEY,
                region=RegionInfo(endpoint=settings.EC2_ENDPOINT),
                is_secure=False,
                port=int(settings.EC2_PORT),
                path=settings.EC2_PATH,
            )
        return self._ec2_conn

    def run(self, instance):
        try:
            reservation = self.ec2_conn.run_instances(
                settings.EC2_AMI,
                key_name=settings.EC2_KEY_NAME,
                security_groups=["default"],
            )
            instance.ec2_id = reservation.instances[0].id
            return True
        except EC2ResponseError as exc:
            logging.error("%s - %s" % (exc.status, exc.reason))
            return False

    def terminate(self, instance):
        terminated = self.ec2_conn.terminate_instances(
                                instance_ids=[instance.ec2_id])
        if instance.ec2_id in [inst.id for inst in terminated]:
            return True
        logging.error("Failed to terminate the machine.")
        return False

    def get(self, instance):
        try:
            reservation = self.ec2_conn.get_all_instances(instance_ids=[instance.ec2_id])
        except EC2ResponseError as exc:
            logging.error("Error getting instance %s: %s - %s" % (instance.ec2_id, exc.status, exc.reason))
            return False
        if reservation and reservation[0].instances:
            ec2_instance = reservation[0].instances[0]
            if ec2_instance.id == instance.ec2_id and ec2_instance.ip_address != ec2_instance.private_ip_address:
                instance.state = ec2_instance.state
                instance.host = ec2_instance.ip_address
                return True
            logging.info("Instance not updated. State: %s, IP: %s." % (ec2_instance.state, ec2_instance.ip_address))
            return False
        logging.error("Instance %s not found." % instance.ec2_id)
        return False

    def authorize(self, instance):
        # FIXME (fsouza): support other groups than default; udp services and multi-port services.
        try:
            return self.ec2_conn.authorize_security_group(
                group_name="default",
                ip_protocol="tcp",
                cidr_ip="%s/32" % (instance.host),
                from_port=instance.port,
                to_port=instance.port,
            )
        except EC2ResponseError as exc:
            logging.error("%s - %s" % (exc.status, exc.reason))
            return False

    def unauthorize(self, instance):
        # FIXME (fsouza): support other groups than default; udp services and multi-port services.
        try:
            return self.ec2_conn.revoke_security_group(
                group_name="default",
                ip_protocol="tcp",
                cidr_ip="%s/32" % (instance.host),
                from_port=instance.port,
                to_port=instance.port,
            )
        except EC2ResponseError as exc:
            logging.error("%s - %s" % (exc.status, exc.reason))
            return False
