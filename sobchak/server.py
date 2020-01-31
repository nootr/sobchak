import logging
from math import atan, sqrt, sin
from novaclient.v2.servers import Server
from sobchak.helper import get_object_by_id

class CustomServer(Server):
    """CustomServer

    A CustomServer object contains information about an OpenStack instance and
    the resources it needs.
    """

    def __init__(self, server, flavors):
        Server.__init__(self, server.manager, server._info)
        self._flavor = get_object_by_id(flavors, self.flavor['id'])
        logging.debug('Initialized server: %s', self.id)

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.__str__()

    def __eq__(self, other):
        return self.id == other.id

    @property
    def ram(self):
        """ram

        Returns the memory which is assigned to this server in MB's.
        """
        return self._flavor.ram

    @property
    def vcpus(self):
        """vcpus

        Returns the number of virtual CPU's which are assigned to this server.
        """
        return self._flavor.vcpus

    @property
    def ratio(self):
        """ratio

        Returns the RAM/vCPU ratio, rounded down to the nearest integer to allow
        ratio comparison as it prevents floating point comparison issues.
        """
        return int(self.ram/self.vcpus)

    @property
    def hypervisor(self):
        """hypervisor

        Returns the hypervisor hostname.
        """
        return self.__getattr__('OS-EXT-SRV-ATTR:hypervisor_hostname')

    @property
    def length(self):
        """length

        Returns the length of this VM's resource vector.
        """
        return sqrt(self.ram * self.ram + self.vcpus * self.vcpus)

    @property
    def active(self):
        """active

        Returns True if this VM's status is "ACTIVE".
        """
        return self.status == 'ACTIVE'

    def calculate_divergence(self, reference):
        """calculate_divergence

        Returns the divergence from a reference slope. See README.md for more
        information about what this actually means.
        """
        angle = atan(self.ratio) - atan(reference)
        return self.length * sin(angle)
