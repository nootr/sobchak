import logging
from math import atan
from novaclient.v2.hypervisors import Hypervisor
from sobchak.helper import sigmoid
from sobchak.plot import Plot

class CustomHypervisor(Hypervisor):
    """CustomHypervisor

    A CustomHypervisor object contains information about its available resources
    and the VMs it hosts.
    """

    def __init__(self, hypervisor, common_ratio, config={}):
        Hypervisor.__init__(self, hypervisor.manager, hypervisor._info)
        self.servers = []
        self._server_snapshot = []
        self._common_ratio = common_ratio
        self._ram_overcommit = config.get('ram_overcommit', 1)
        self._cpu_overcommit = config.get('cpu_overcommit', 4)
        self._memory_overhead = config.get('hypervisor_memory_overhead', 32768)
        self._gave_cpu_warning = False
        self._gave_ram_warning = False
        logging.debug('Initialized hypervisor: %s', self.id)

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.__str__()

    def snapshot(self, validate=True):
        """snapshot

        Saves the current VM list.
        """
        self._server_snapshot.append([s for s in self.servers])
        if validate:
            self.verify_available_resources()

    def use_snapshot(self, index=-1, validate=True):
        """use_snapshot

        Resets the VM list to the last snapshot.
        """
        self.servers = [s for s in self._server_snapshot[index]]
        if validate:
            self.verify_available_resources()

    def verify_available_resources(self):
        """verify_available_resources

        Checks if OpenStack agrees with our calculated available resources.
        """
        available_vcpus_check = self.vcpus * self._cpu_overcommit \
            - self.vcpus_used
        if not self.available_vcpus == available_vcpus_check:
            logging.error('Calculated available VCPUs (%i) is not %i',
                          self.available_vcpus, available_vcpus_check)
            logging.error('Please check the configuration.')
            exit(1)

        available_ram_check = self.memory_mb * self._ram_overcommit \
            - self.memory_mb_used
        if not self.available_ram == available_ram_check:
            logging.error('Calculated available RAM (%i) is not %i',
                          self.available_vcpus, available_vcpus_check)
            logging.error('Please check the configuration.')
            exit(1)

    def to_dict(self):
        """to_dict

        Returns the hypervisor as a dict.
        """
        dictionary = {
            'name': self.name,
            'score': self.score,
            'divergence': self.divergence,
            'enabled': self.enabled,
            'vcpus': self.vcpus * self._cpu_overcommit,
            'vcpus_used': self.vcpus_used,
            'memory_mb': self.memory_mb * self._ram_overcommit,
            'memory_mb_used': self.memory_mb_used,
            'vms': [s.name for s in self.servers],
        }
        return dictionary

    @property
    def plot(self, include_snapshot=True):
        """plot

        Generates a plot of the hypervisor and its resources and returns it as a
        Base64 decoded string.

        Warning: enabling `include_snapshot` will actually revert the hypervisor
        to the last snapshot!
        """
        # Generate a plot
        width = self.memory_mb * self._ram_overcommit - self._memory_overhead
        height = self.vcpus * self._cpu_overcommit
        plot = Plot(width, height, self.name, 'memory [MB]', 'VCPUs')

        # Draw graphs representing VMs
        def _generate_data(servers):
            x = [i for i in range(width)]
            y = [0]
            for vm in servers:
                dy_dx = vm.vcpus / vm.ram
                for _ in range(vm.ram):
                    y.append(y[-1] + dy_dx)
            return x, y

        x, y = _generate_data(self.servers)
        plot.add_graph(x, y, 'Hosted VMs (after)')

        if include_snapshot:
            self.use_snapshot(0)
            x, y = _generate_data(self.servers)
            plot.add_graph(x, y, 'Hosted VMs (before)')

        # Grey-out graph if hypervisor is disabled
        if not self.enabled:
            plot.add_box(1.1*width, 1.1*height, facecolor=(0.8,)*3)

        # Draw box representing hypervisor resources
        plot.add_box(width, height, 'Available resources')

        # Draw graphs representing common ratio
        dx = self._common_ratio
        x = []
        y = []
        next_x = width
        next_y = height
        while next_x >= 0 and next_y >= 0:
            x.append(next_x)
            y.append(next_y)
            next_x -= dx
            next_y -= 1
        plot.add_graph(x, y, 'Most common resource ratio')

        return plot.base64

    @property
    def name(self):
        """name

        Returns the hypervisor domain name.
        """
        return self.hypervisor_hostname

    @property
    def enabled(self):
        """enabled

        Returns True if the hypervisor is enabled.
        """
        return self.status == 'enabled'

    @property
    def available_ram(self):
        """available_ram

        Returns the amount of available RAM in MB's, taking memory overhead and
        the overcommit ratio into account. Note that memory overhead is already
        calculated into `self.memory_mb_used`.
        """
        available_ram = self.memory_mb * self._ram_overcommit \
            - sum([vm.ram for vm in self.servers]) - self._memory_overhead

        if available_ram < 0 and not self._gave_ram_warning:
            logging.warning('Used memory above overcommit treshold on %s',
                            self.name)
            self._gave_ram_warning = True

        return available_ram

    @property
    def available_vcpus(self):
        """available_vcpus

        Returns the number of available VCPU's.
        """
        available_vcpus = self.vcpus * self._cpu_overcommit \
            - sum([vm.vcpus for vm in self.servers])

        if available_vcpus < 0 and not self._gave_cpu_warning:
            logging.warning('Used vCPUS above overcommit treshold on %s',
                            self.name)
            self._gave_cpu_warning = True

        return available_vcpus

    @property
    def ratio(self):
        """ratio

        Returns the ratio between the available RAM (in MB's) and the available
        number of vCPU's.
        """
        if not self.available_vcpus:
            return self.available_ram
        return int(self.available_ram / self.available_vcpus)

    @property
    def divergence(self):
        """divergence

        Returns a tuple containing the sum of left- and right-handed divergent
        VMs.
        """
        left = right = 0
        for vm in self.servers:
            divergence = vm.calculate_divergence(self._common_ratio)
            if divergence < 0:
                left -= divergence
            else:
                right += divergence
        return (left, right)

    @property
    def score(self):
        """score

        Returns a score based on the difference between the most common RAM/vCPU
        ratio amongst VMs and the RAM/vCPU ratio of available resources of this
        hypervisor. The closer to zero, the better the score.
        """
        # TODO: Account for CPU/RAM cost
        weight_ram = sigmoid(self.available_ram / self.memory_mb)
        weight_vcpus = sigmoid(self.available_vcpus / self.vcpus)
        angle = atan(self._common_ratio) - atan(self.ratio)
        return angle * (weight_ram + weight_vcpus)

    def pop(self):
        """pop

        Returns all servers and removes them from this hypervisor.
        """
        servers = self.servers
        self.servers = []
        return servers

    def add_server(self, server, force=False):
        """add_server

        Adds an OpenStack instance to the Hypervisor. Returns True if succeeded,
        else returns False.
        """
        if not force and (server.ram > self.available_ram or
                          server.vcpus > self.available_vcpus):
            return False
        logging.debug('Adding %s to %s', server.name, self)
        self.servers.append(server)
        return True

    def remove_server(self, server):
        """remove_server

        Removes a given VM from this hypervisor. Returns True on success,
        otherwise (e.g. if the VM wasn't found on this server) returns False.
        """
        logging.debug('Removing %s from %s', server.name, self)
        filtered_servers = [s for s in self.servers if not s == server]
        if len(filtered_servers) == len(self.servers) - 1:
            self.servers = filtered_servers
            return True
        else:
            logging.error('Error while removing server %s: VM count %i -> %i',
                          server.name, len(self.servers), len(filtered_servers))
            return False
