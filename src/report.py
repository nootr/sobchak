import os
import logging

class Report(object):
    """Report

    A Report object generates a report in the form of a HTML-page of a list of
    hypervisors and information about how certain migrations improve the
    resource distribution.
    """

    def __init__(self, inventory, template='template.html'):
        self._inventory = inventory
        self._migration_report = ''
        self._template = self._fetch_template(template)
        self.title = 'Migration report'

    def _fetch_template(self, filename):
        """_fetch_template

        Reads a template and returns the contents.
        """
        try:
            with open(filename, 'r') as template:
                return template.read()
        except Exception as e:
            logging.error('Could not load %s: %s', filename, e)
            exit(1)

    def add_migrations(self, migrations):
        """add_migrations

        Adds the migrations to the report.
        """
        def code_block(c):
            return '<pre><code>' + c + '</code></pre>'

        migration_list = '<br />'.join([str(m) for m in migrations])
        self._migration_report = code_block(migration_list)

    def save(self, filename='report.html'):
        """save

        Save the report as a HTML-file.
        """
        with open(filename, 'w+') as f:
            f.write(self.page)
            print('Report available: {}'.format(os.path.abspath(filename)))

    @property
    def body(self):
        """body

        Returns the HTML body of the report.
        """
        def img_tag(i): return \
            '<img width="25%" src="data:image/png;base64,{}"/>'.format(i)

        body = '<h1>{}</h1>'.format(self.title)

        body += '<h2>Hypervisor info</h2>'
        for hypervisor in self._inventory.hypervisors:
            body += img_tag(hypervisor.plot)

        body += '<h2>Migration list</h2>'
        body += self._migration_report

        return body

    @property
    def page(self):
        """page

        Returns the report as HTML.
        """
        variables = {
            'title': self.title,
            'body': self.body
        }
        content = self._template

        for key, value in variables.items():
            content = content.replace('{{'+key+'}}', value)

        return content
