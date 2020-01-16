import os
import logging
from novaclient import client as nova_client
from keystoneauth1 import session as keystone_session
from keystoneclient.v3 import client as keystone_client
from keystoneauth1 import session as keystone_session
from keystoneauth1.identity import v3

try:
    PROJECT_ID = os.environ['OS_PROJECT_ID']
    AUTH_URL = os.environ['OS_AUTH_URL']
    USERNAME = os.environ['OS_USERNAME']
    PASSWORD = os.environ['OS_PASSWORD']
except KeyError:
    logging.error('Please source your OpenStack openrc file.')
    raise

class Session(keystone_session.Session):
    """Session

    Maintains an OpenStack Keystone session and provides a Keystone and a Nova
    client.
    """

    def __init__(self):
        auth = v3.Password(
            auth_url=AUTH_URL,
            username=USERNAME,
            password=PASSWORD,
            project_id=PROJECT_ID,
            user_domain_name='Default')
        keystone_session.Session.__init__(self, auth=auth)
        self.keystone_client = keystone_client.Client(session=self)
        self.nova_client = nova_client.Client('2', session=self)
