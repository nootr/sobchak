import logging
from src.helper import get_object_by_id
from src.hypervisor import CustomHypervisor
from src.server import CustomServer
from src.migration import Migration

class Inventory(object):
    """Inventory

    An object containing Hypervisor and VM objects which are fetched using the
    OpenStack API.
    """

    def __init__(self, novaclient, config={}):
        self._client = novaclient
        self._config = config
        self._hypervisors = []
        self._vms = []
        self._flavors = []

    def to_dict(self):
        """to_dict

        Returns the inventory as a dictionary.
        """
        return {
            'common_ratio': self.common_ratio,
            'inventory': [h.to_dict() for h in self.hypervisors]
        }

    def snapshot(self, validate=True):
        """snapshot

        Saves a snapshot of the current inventory.
        """
        logging.debug('Taking snapshot')
        for hypervisor in self.hypervisors:
            hypervisor.snapshot(validate)

    def use_snapshot(self, index=-1, validate=True):
        """use_snapshot

        Reverts to the last snapshot.
        """
        logging.debug('Reverting to snapshot')
        for hypervisor in self.hypervisors:
            hypervisor.use_snapshot(index, validate)

    @property
    def hypervisors(self):
        """hypervisors

        Returns a list of hypervisors as CustomHypervisor objects. If it's the
        first time the list is being called, the VM's are attached to their
        hypervisors.
        """
        if not self._hypervisors:
            logging.info('Fetching hypervisor info')
            self._hypervisors = [
                CustomHypervisor(h, self.common_ratio, self._config)
                for h in self._client.hypervisors.list()]

            for vm in self.vms:
                hypervisor = get_object_by_id(self._hypervisors, vm.hypervisor)
                if hypervisor:
                    hypervisor.add_server(vm, force=True)
                else:
                    logging.warning('Unknown hypervisor for %s (status: %s)',
                                    vm, vm.status)

            self.snapshot()

        return self._hypervisors

    @property
    def vms(self):
        """vms

        Returns a list of VM's as CustomServer objects.
        """
        def _fetch_vms(client, chunksize=1000):
            """_fetch_vms

            Fetches and returns a list of all servers using pagination.
            """
            vms = []
            listmarker = None
            while True:
                new_vms = client.servers.list(
                    search_opts={'all_tenants': True},
                    limit=chunksize,
                    marker=listmarker)
                vms.extend(new_vms)
                if len(new_vms) < chunksize:
                    break
                else:
                    listmarker = vms[-1].id
            return vms

        if not self._vms:
            logging.info('Fetching VM info')
            self._vms = [CustomServer(vm, self.flavors)
                         for vm in _fetch_vms(self._client)
                         if vm.status != 'SHELVED_OFFLOADED']

        return self._vms

    @property
    def enabled_hypervisors(self):
        """enabled_hypervisors

        Returns a list of enabled hypervisors.
        """
        return [h for h in self.hypervisors if h.enabled]

    @property
    def left_divergent(self):
        """left_divergent

        Returns the enabled hypervisor which is the most divergent to the left
        and has a negative score, so it can help. Returns None if no hypervisors
        fit that profile.
        """
        candidate_hypervisors = [h for h in self.enabled_hypervisors
                                 if h.score < 0]
        if candidate_hypervisors:
            return max(candidate_hypervisors, key=lambda h: h.divergence[0])
        else:
            return None

    @property
    def right_divergent(self):
        """right_divergent

        Returns the enabled hypervisor which is the most divergent to the right
        and has a positive score, so it can help. Returns None if no hypervisors
        fit that profile.
        """
        candidate_hypervisors = [h for h in self.enabled_hypervisors
                                 if h.score > 0]
        if candidate_hypervisors:
            return max(candidate_hypervisors, key=lambda h: h.divergence[1])
        else:
            return None

    @property
    def common_ratio(self):
        """common_ratio

        Returns the most common ratio amongst all VMs.
        """
        ratios = [vm.ratio for vm in self.vms]
        return max(ratios, key=ratios.count)

    @property
    def flavors(self):
        """flavors

        Returns a list of Flavors.
        """
        if not self._flavors:
            self._flavors = self._client.flavors.list(is_public=None)

        return self._flavors

    def _validate_migrations(self, migrations):
        """_validate_migrations

        Validate a list of migrations on several points:

        * No duplicate VMs
        * Migrations - in order - are possible after last snapshot
        * Same amount of VMs
        * Disabled hypervisors are left alone
        """
        self.use_snapshot(0)

        # Check for duplicate VMs
        vm_ids = [vm.id for vm in self.vms]
        assert len(vm_ids) == len(set(vm_ids))

        number_of_vms = len(self.vms)

        # Check for valid migration list
        for migration in migrations:
            assert migration.source.enabled
            assert migration.destination.enabled
            assert migration.source.remove_server(migration.server)
            assert migration.destination.add_server(migration.server)

        # Check for number of VMs
        assert number_of_vms == len(self.vms)

        # Check for duplicate VMs
        vm_ids = [vm.id for vm in self.vms]
        assert len(vm_ids) == len(set(vm_ids))

        logging.info('Validated migration list')

    def _increase_buffer(self, hypervisor, skip_hypervisor_ids=[],
                         skip_server_ids=[]):
        """_increase_buffer

        Returns a migration which will temporarily give a given hypervisor extra
        available resources. Does not use the hypervisors given in `skip` as a
        buffer.
        """
        potential_buffers = [h for h in self.enabled_hypervisors
                             if h.id not in skip_hypervisor_ids and
                             h.id != hypervisor.id]
        servers = [s for s in hypervisor.servers if s.id not in skip_server_ids]

        buffers = reversed(sorted(potential_buffers,
                                  key=lambda h: h.available_vcpus * h.available_ram))

        sorted_servers = reversed(sorted(servers, key=lambda s: s.length))

        for buff in buffers:
            for server in sorted_servers:
                if buff.add_server(server):
                    assert hypervisor.remove_server(server)
                    return Migration(server, hypervisor, buff)

        logging.warning('Could not find available resources to migrate!')
        return None

    def _try_migration(self, migration):
        """_try_migration

        Tries a migration and adds a migration to a buffer hypervisor if needed.
        Returns a tuple containing lists of migrations and optional post
        migrations.
        """
        assert migration.source.remove_server(migration.server)
        migrations = []
        post_migrations = []
        while not migration.destination.add_server(migration.server):
            logging.info('Unable to migrate server %s, adding buffer.',
                         migration.server)
            buffer_migration = self._increase_buffer(migration.destination,
                                                     skip_hypervisor_ids=[
                                                         migration.source.id],
                                                     skip_server_ids=[migration.server.id])
            if buffer_migration:
                migrations.append(buffer_migration)
                post_migrations.append(buffer_migration.reverse)
            else:
                migration.source.add_server(migration.server)
                return None
        migrations.append(migration)
        return (migrations, post_migrations)

    def _plan_migrations(self, needed_migrations):
        """_plan_migrations

        Takes a list of Migration objects and determines which actual migrations
        need to be done to realize this (as some migrations will not be possible
        due to insufficient available resources). Returns a list of Migration
        objects or an empty list if it's not possible.
        """
        migrations = []
        skip_servers = []

        for migration in needed_migrations:
            if migration.server in skip_servers:
                skip_servers.remove(migration.server)
                continue
            new_migrations = self._try_migration(migration)
            if not new_migrations:
                logging.warning('Could not get enough free resources.')
                self.use_snapshot()
                return []
            new_migration, post_migrations = new_migrations
            migrations.extend(new_migration)
            for post_migration in post_migrations:
                if post_migration.server in [m.server for m in
                                             needed_migrations if m not in migrations]:
                    skip_servers.append(post_migration.server)
                    destinations = [m.destination for m in needed_migrations
                                    if m.server == post_migration.server]
                    assert len(destinations) == 1
                    post_migration.destination = destinations[0]
                needed_migrations.append(post_migration)

        return migrations

    def _score_with_vm(self, hypervisor, vm):
        """_score_with_vm

        Returns the score a hypervisor would have if it hosted a given VM.
        """
        if not hypervisor.add_server(vm):
            return hypervisor.score
        else:
            score = hypervisor.score
            assert hypervisor.remove_server(vm)
            return score

    def _mix_hypervisors(self, subject, improvement):
        """_mix_hypervisors

        Takes two hypervisors (a `subject` which is to be improved and an
        `improvement` which has the divergence which enables the improvement)
        and mixes their VMs to improve the overall score.

        Returns a list of migrations if the combined score is lowered, otherwise
        returns None. Also returns None if the VMs do not fit on the two
        hypervisors (e.g. due to bad scheduling).

        Note that the list of migrations that is generated does not take
        hypervisor resources into account, so shuffling between a third node is
        needed when there's not enough free resources to migrate certain VMs.
        """
        logging.info('Mixing %s and %s', subject.name, improvement.name)
        score_before = abs(subject.score) + abs(improvement.score)
        subject_vms = subject.pop()
        improvement_vms = improvement.pop()
        vms = subject_vms + improvement_vms

        while vms:
            best_vm = min(vms,
                          key=lambda vm: abs(self._score_with_vm(subject, vm)))
            if not subject.add_server(best_vm):
                break
            vms.remove(best_vm)

        for vm in vms:
            if not improvement.add_server(vm):
                logging.warning('Could not fit VMs in hypervisors!')
                subject.servers = subject_vms
                improvement.servers = improvement_vms
                return None

        score_after = abs(subject.score) + abs(improvement.score)
        logging.info('Score from %f to %f', score_before, score_after)
        if score_after >= score_before:
            subject.servers = subject_vms
            improvement.servers = improvement_vms
            return None

        return [Migration(s, improvement, subject) for s in subject.servers
                if s not in subject_vms] + \
               [Migration(s, subject, improvement) for s in improvement.servers
                if s not in improvement_vms]

    def optimize(self, migrations=[], iterations=3):
        """optimize

        Generates and returns a list of migrations to improve Hypervisor
        resource distribution.
        """
        if iterations == 0:
            return migrations

        for subject in reversed(sorted(self.enabled_hypervisors,
                                       key=lambda h: abs(h.score))):
            if subject.score < 0:
                improvement = self.right_divergent
            else:
                improvement = self.left_divergent

            if not improvement:
                continue

            needed_migrations = self._mix_hypervisors(subject, improvement)
            self.use_snapshot(validate=False)
            if needed_migrations:
                migrations.extend(self._plan_migrations(needed_migrations))

                # Final optimization; merge successive migrations of the same VM
                optimizing = True
                while optimizing:
                    optimizing = False
                    for i in range(len(migrations) - 1):
                        if migrations[i].server == migrations[i+1].server:
                            optimizing = True
                            migrations = migrations[:i] + \
                                [Migration(migrations[i].server,
                                           migrations[i].source,
                                           migrations[i+1].destination)] + \
                                migrations[i+2:]
                            break

                self.snapshot(validate=False)
                self._validate_migrations(migrations)
                return self.optimize(migrations=migrations,
                                     iterations=iterations-1)

        return migrations
