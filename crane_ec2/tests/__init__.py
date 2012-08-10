import mocker

from boto.ec2.regioninfo import RegionInfo
from boto.exception import EC2ResponseError
from django.conf import settings

from crane_ec2 import Client
from crane_ec2.tests import mocks


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
    port = "22"
    saved = False
    deleted = False

    def __init__(self, name=None, ec2_id=None, **kwargs):
        self.name = name
        self.ec2_id = ec2_id
        self.pk = 1
        for k, v in kwargs:
            setattr(self, k, v)


class EC2ClientTestCase(mocker.MockerTestCase):

    def tearDown(self):
        self.mocker.reset()

    def test_ec2_conn_connects_to_ec2_using_data_from_settings_when_not_connected(self):
        fake = mocks.FakeEC2Conn()
        r = RegionInfo()
        regioninfo = self.mocker.replace("boto.ec2.regioninfo.RegionInfo")
        regioninfo(endpoint=settings.EC2_ENDPOINT)
        self.mocker.result(r)
        connect_ec2 = self.mocker.replace("boto.connect_ec2")
        connect_ec2(
            aws_access_key_id=settings.EC2_ACCESS_KEY,
            aws_secret_access_key=settings.EC2_SECRET_KEY,
            region=r,
            is_secure=False,
            port=int(settings.EC2_PORT),
            path=settings.EC2_PATH,
        )
        self.mocker.result(fake)
        self.mocker.replay()
        client = Client()
        conn = client.ec2_conn
        self.assertIsInstance(conn, mocks.FakeEC2Conn)
        self.mocker.verify()

    def test_run_creates_instance_with_data_from_settings_without_saving_it_in_the_database(self):
        instance = Instance(name="professor_xavier")
        client = Client()
        client._ec2_conn = mocks.FakeEC2Conn()
        ran = client.run(instance)
        self.assertTrue(ran)
        self.assertEqual("i-00000302", instance.ec2_id)
        self.assertFalse(instance.saved)

    def test_run_returns_False_and_does_not_save_the_instance_in_the_database_if_it_fails_to_boot(self):
        instance = Instance(name="far_cry")
        client = Client()
        client._ec2_conn = mocks.FailingEC2Conn()
        ran = client.run(instance)
        self.assertFalse(ran)
        self.assertIsNone(instance.ec2_id)

    def test_run_loggs_the_exception_if_it_fails_to_start_the_machine(self):
        err = self.mocker.replace("logging.error")
        err("500 - Failed")
        self.mocker.result(None)
        self.mocker.replay()
        instance = Instance(name="far_cry")
        client = Client()
        client._ec2_conn = mocks.FailingEC2Conn()
        client.run(instance)
        self.mocker.verify()

    def test_terminate_removes_ec2_instance(self):
        instance = Instance(name="professor_xavier")
        client = Client()
        client._ec2_conn = mocks.FakeEC2Conn()
        ran = client.run(instance)
        self.assertTrue(ran)

        ran = client.terminate(instance)
        self.assertEqual(["i-00000302"], client._ec2_conn.terminated)
        self.assertTrue(ran)

    def test_terminate_returns_false_when_cannot_remove_ec2_instance(self):
        instance = Instance(name="professor_xavier")
        client = Client()
        client._ec2_conn = mocks.FakeEC2Conn()
        ran = client.run(instance)
        self.assertTrue(ran)
        client._ec2_conn = mocks.FailingEC2Conn()
        ran = client.terminate(instance)
        self.assertFalse(ran)

    def test_terminate_loggs_the_exception_if_it_fails_to_terminate_the_machine(self):
        instance = Instance(name="daniel_gildenlow")
        err = self.mocker.replace("logging.error")
        err("Failed to terminate the machine.")
        self.mocker.result(None)
        self.mocker.replay()
        client = Client()
        client._ec2_conn = mocks.FailingEC2Conn()
        client.terminate(instance)
        self.mocker.verify()

    def test_get_instance_should_set_instance_state_and_ip_when_its_ready_and_return_True_if_its_ok(self):
        instance = Instance(name="good_news_first", ec2_id="i-00000302")
        client = Client()
        client._ec2_conn = mocks.FakeEC2Conn(times_to_fail=0)
        changed = client.get(instance)
        self.assertTrue(changed)
        self.assertEqual("running", instance.state)
        self.assertEqual("10.10.10.10", instance.host)

    def test_get_instance_should_return_false_if_instance_is_not_running_or_does_not_have_public_ip_yet(self):
        instance = Instance(name="good_news_first", ec2_id="i-00000302")
        client = Client()
        client._ec2_conn = mocks.FakeEC2Conn(times_to_fail=1)
        changed = client.get(instance)
        self.assertFalse(changed)

    def test_get_instance_should_log_instance_not_found_if_instance_is_not_found(self):
        instance = Instance(name="good_news_first", ec2_id="i-00000302")
        err = self.mocker.replace("logging.error")
        err("Instance %s not found." % instance.ec2_id)
        self.mocker.result(None)
        self.mocker.replay()
        client = Client()
        client._ec2_conn = mocks.FailingEC2Conn()
        changed = client.get(instance)
        self.assertFalse(changed)
        self.mocker.verify()

    def test_get_instance_should_log_instance_not_found_with_exception_in_case_of_any_exception(self):
        def fail_to_get(*args, **kwargs):
            raise EC2ResponseError(status=400, reason="What???")
        instance = Instance(name="good_news_first", ec2_id="i-00000302")
        err = self.mocker.replace("logging.error")
        err("Error getting instance i-00000302: 400 - What???")
        self.mocker.result(None)
        self.mocker.replay()
        client = Client()
        client._ec2_conn = mocks.FailingEC2Conn()
        client._ec2_conn.get_all_instances = fail_to_get
        changed = client.get(instance)
        self.assertFalse(changed)
        self.mocker.verify()

    def test_get_instance_should_log_instance_not_running_yet_with_notice(self):
        instance = Instance(name="good_news_first", ec2_id="i-00000302")
        info = self.mocker.replace("logging.info")
        info("Instance i-00000302 not updated. State: running, IP: 172.16.52.10.")
        self.mocker.result(None)
        self.mocker.replay()
        client = Client()
        client._ec2_conn = mocks.FakeEC2Conn(times_to_fail=1)
        client.get(instance)
        self.mocker.verify()

    def test_authorize_should_use_ec2_conn_to_authorize_access_to_the_instance(self):
        fake = mocks.FakeEC2Conn()
        instance = Instance(name="tides_of_time", ec2_id="i-021")
        client = Client()
        client._ec2_conn = fake
        authorized = client.authorize(instance)
        self.assertTrue(authorized)
        authorization_string = "cidr_ip=%s/32 from_port=%s group_name=default ip_protocol=tcp to_port=%s" % (
            instance.host,
            instance.port,
            instance.port,
        )
        self.assertIn(authorization_string, fake.authorizations)

    def test_authorize_should_return_False_if_it_fails_to_authorize(self):
        instance = Instance(name="semblance_of_liberty", ec2_id="i-022")
        client = Client()
        client._ec2_conn = mocks.FailingEC2Conn()
        authorized = client.authorize(instance)
        self.assertFalse(authorized)

    def test_authorize_should_return_False_when_ec2_conn_raises_exception(self):
        def fail_to_authorize(*args, **kwargs):
            raise EC2ResponseError(status=500, reason="I've failed, my friend")
        instance = Instance(name="semblance_of_liberty", ec2_id="i-022")
        client = Client()
        client._ec2_conn = mocks.FakeEC2Conn()
        client._ec2_conn.authorize_security_group = fail_to_authorize
        authorized = client.authorize(instance)
        self.assertFalse(authorized)

    def test_authorize_should_log_exceptions_from_ec2_conn(self):
        def fail_to_authorize(*args, **kwargs):
            raise EC2ResponseError(status=500, reason="I've failed, my friend")
        err = self.mocker.replace("logging.error")
        err("500 - I've failed, my friend")
        self.mocker.result(None)
        self.mocker.replay()
        instance = Instance(name="semblance_of_liberty", ec2_id="i-022")
        client = Client()
        client._ec2_conn = mocks.FakeEC2Conn()
        client._ec2_conn.authorize_security_group = fail_to_authorize
        client.authorize(instance)
        self.mocker.verify()

    def test_unauthorize_should_use_ec2_to_revoke_access_to_the_instance(self):
        fake = mocks.FakeEC2Conn()
        instance = Instance(name="tides_of_time", ec2_id="i-021")
        client = Client()
        client._ec2_conn = fake
        authorized = client.authorize(instance)
        self.assertTrue(authorized)
        unauthorized = client.unauthorize(instance)
        self.assertTrue(unauthorized)
        authorization_string = "cidr_ip=%s/32 from_port=%s group_name=default ip_protocol=tcp to_port=%s" % (
            instance.host,
            instance.port,
            instance.port,
        )
        self.assertNotIn(authorization_string, fake.authorizations)

    def test_unauthorize_should_return_False_when_revoking_fail_at_ec2_conn(self):
        instance = Instance()
        client = Client()
        client._ec2_conn = mocks.FailingEC2Conn()
        self.assertFalse(client.unauthorize(instance))

    def test_unauthorize_should_return_False_when_ec2_conn_raises_exception(self):
        def fail_to_authorize(*args, **kwargs):
            raise EC2ResponseError(status=500, reason="I've failed, my friend")
        instance = Instance(name="semblance_of_liberty", ec2_id="i-022")
        client = Client()
        client._ec2_conn = mocks.FakeEC2Conn()
        client._ec2_conn.revoke_security_group = fail_to_authorize
        self.assertFalse(client.unauthorize(instance))

    def test_unauthorize_should_log_failure_when_ec2_conn_raises_exception(self):
        def fail_to_authorize(*args, **kwargs):
            raise EC2ResponseError(status=500, reason="I've failed, my friend")
        err = self.mocker.replace("logging.error")
        err("500 - I've failed, my friend")
        self.mocker.result(None)
        self.mocker.replay()
        instance = Instance(name="semblance_of_liberty", ec2_id="i-022")
        client = Client()
        client._ec2_conn = mocks.FakeEC2Conn()
        client._ec2_conn.revoke_security_group = fail_to_authorize
        client.unauthorize(instance)
        self.mocker.verify()
