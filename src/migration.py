class Migration(object):
    """Migration

    Contains information about a migration; a VM, a source and a destination.
    """

    def __init__(self, server, source, destination):
        self.server = server
        self.source = source
        self.destination = destination

    def __str__(self):
        args = [
            '--live-migration',
            '--host {}'.format(self.destination.name),
        ]
        comment = '#{}:{}>{}'.format(
            self.server, self.source, self.destination)
        return 'openstack server migrate {} {} {}'.format(
            ' '.join(args), self.server.id, comment)

    def __repr__(self):
        return self.__str__()

    @property
    def reverse(self):
        """reverse

        Returns the opposite migration.
        """
        return Migration(self.server, self.destination, self.source)
