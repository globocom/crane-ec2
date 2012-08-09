from boto.ec2.instance import Instance, Reservation
from boto.exception import EC2ResponseError


def build_pending_reservations(instance_id):
    instance = Instance()
    instance.id = instance_id
    instance.state = 'running'
    instance.ip_address = '172.16.52.10'
    instance.private_ip_address = '172.16.52.10'
    r = Reservation()
    r.instances = [instance]
    return [r]


def build_running_reservations(instance_id):
    instance = Instance()
    instance.id = instance_id
    instance.state = 'running'
    instance.ip_address = '10.10.10.10'
    instance.private_ip_address = '172.16.52.10'
    r = Reservation()
    r.instances = [instance]
    return [r]


class FakeEC2Conn(object):

    def __init__(self, times_to_fail=1, *args, **kwargs):
        self.authorizations = []
        self.instances = []
        self.terminated = []
        self.args = args
        self.kwargs = kwargs
        self.times_to_fail = times_to_fail
        self.fails = 0

    def run_instances(self, ami, *args, **kwargs):
        self.instances.append("instance with ami %s and key %s and groups %s" % (
            ami,
            kwargs["key_name"],
            ", ".join(kwargs["security_groups"])
        ))
        instance = Instance()
        instance.id = 'i-00000302'
        reservation = Reservation()
        reservation.instances = [instance]
        return reservation

    def terminate_instances(self, instance_ids):
        self.terminated.extend(instance_ids)
        instances = []
        for instance_id in instance_ids:
            instance = Instance()
            instance.id = instance_id
            instances.append(instance)
        return instances

    def get_all_instances(self, instance_ids, *args, **kwargs):
        if self.fails < self.times_to_fail:
            self.fails += 1
            return build_pending_reservations(instance_ids[0])
        return build_running_reservations(instance_ids[0])

    def _build_authorization_string(self, kw):
        items = ["%s=%s" % (k, v) for k, v in kw.iteritems()]
        return " ".join(sorted(items))

    def authorize_security_group(self, *args, **kwargs):
        self.authorizations.append(self._build_authorization_string(kwargs))
        return True

    def revoke_security_group(self, *args, **kwargs):
        self.authorizations.remove(self._build_authorization_string(kwargs))
        return True


class FailingEC2Conn(FakeEC2Conn):

    def run_instances(self, *args, **kwargs):
        raise EC2ResponseError(status=500, reason="Failed")

    def terminate_instances(self, instance_ids):
        return []

    def get_all_instances(self, *args, **kwargs):
        return []

    def authorize_security_group(self, *args, **kwargs):
        return False

    def revoke_security_group(self, *args, **kwargs):
        return False
