import unittest

from boto.ec2.regioninfo import RegionInfo
from django.conf import settings
from mocker import Mocker

from ec2 import Client
from ec2.tests import mocks


class FakeManager(object):

    def create(self, **kwargs):
        return Instance(**kwargs)

    def get(self, **kwargs):
        return Instance(**kwargs)


class Instance(object):

    objects = FakeManager()
    pk = None
    state = "running"
    host = "10.10.10.10"
    saved = None
    deleted = None

    def __init__(self, name=None, ec2_id=None, **kwargs):
        self.name = name
        self.ec2_id = ec2_id
        self.pk = 1
        for k, v in kwargs:
            setattr(self, k, v)

    def save(self):
        self.saved = True

    def delete(self):
        self.deleted = True


class EC2ClientTestCase(unittest.TestCase):

    def test_ec2_conn_connects_to_ec2_using_data_from_settings_when_not_connected(self):
        fake = mocks.FakeEC2Conn()
        mocker = Mocker()
        r = RegionInfo()
        regioninfo = mocker.replace("boto.ec2.regioninfo.RegionInfo")
        regioninfo(endpoint=settings.EC2_ENDPOINT)
        mocker.result(r)
        connect_ec2 = mocker.replace("boto.connect_ec2")
        connect_ec2(
            aws_access_key_id=settings.EC2_ACCESS_KEY,
            aws_secret_access_key=settings.EC2_SECRET_KEY,
            region=r,
            is_secure=False,
            port=settings.EC2_PORT,
            path=settings.EC2_PATH,
        )
        mocker.result(fake)
        mocker.replay()
        client = Client()
        conn = client.ec2_conn
        self.assertIsInstance(conn, mocks.FakeEC2Conn)
        mocker.verify()

    def test_run_creates_instance_with_data_from_settings_and_save_it_in_the_database(self):
        instance = Instance(name="professor_xavier")
        client = Client()
        client._ec2_conn = mocks.FakeEC2Conn()
        ran = client.run(instance)
        self.assertTrue(ran)
        self.assertTrue(instance.saved)

    def test_run_returns_False_and_does_not_save_the_instance_in_the_database_if_it_fails_to_boot(self):
        instance = Instance(name="far_cry")
        client = Client()
        client._ec2_conn = mocks.FailingEC2Conn()
        ran = client.run(instance)
        self.assertFalse(ran)

    def test_terminate_removes_instance_from_database(self):
        instance = Instance(name="professor_xavier")
        client = Client()
        client._ec2_conn = mocks.FakeEC2Conn()
        ran = client.run(instance)
        self.assertTrue(ran)

        client.terminate(instance)
        self.assertTrue(instance.deleted)

    def test_terminate_removes_ec2_instance(self):
        instance = Instance(name="professor_xavier")
        client = Client()
        client._ec2_conn = mocks.FakeEC2Conn()
        ran = client.run(instance)
        self.assertTrue(ran)

        ran = client.terminate(instance)
        self.assertEqual(["i-00000302"], client._ec2_conn.terminated)
        self.assertTrue(ran)

    def test_terminate_returns_false_and_doesnt_removes_from_db_when_cannot_remove_ec2_instance(self):
        instance = Instance(name="professor_xavier")
        client = Client()
        client._ec2_conn = mocks.FakeEC2Conn()

        ran = client.run(instance)
        self.assertTrue(ran)

        client._ec2_conn = mocks.FailingEC2Conn()
        ran = client.terminate(instance)
        self.assertFalse(ran)
        self.assertFalse(instance.deleted)

    def test_get_instance_should_set_instance_state_and_ip_when_its_ready_and_return_True_if_its_ok(self):
        instance = Instance(name="good_news_first", ec2_id="i-00000302")
        client = Client()
        client._ec2_conn = mocks.FakeEC2Conn(times_to_fail=0)
        changed = client.get(instance)
        self.assertTrue(changed)
        self.assertTrue(instance.save)
        self.assertEqual("running", instance.state)
        self.assertEqual("10.10.10.10", instance.host)

    def test_get_instance_should_return_false_if_instance_is_not_running_or_does_not_have_public_ip_yet(self):
        instance = Instance(name="good_news_first", ec2_id="i-00000302")
        client = Client()
        client._ec2_conn = mocks.FakeEC2Conn(times_to_fail=1)
        changed = client.get(instance)
        self.assertFalse(changed)
