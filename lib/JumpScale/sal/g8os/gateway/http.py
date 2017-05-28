from JumpScale.sal.g8os.gateway import templates
import signal


class HTTPServer:
    def __init__(self, container, httpproxies):
        self.container = container
        self.httpproxies = httpproxies

    def apply_rules(self):
        # caddy
        caddyconfig = templates.render('caddy.conf', httpproxies=self.httpproxies)
        self.container.upload_content('/etc/caddy.conf', caddyconfig)
        job = self.get_job()
        if job:
            self.container.client.job.kill(job['cmd']['id'], int(signal.SIGHUP))
        else:
            self.container.client.system('caddy -agree -conf /etc/caddy.conf')

    def get_job(self):
        for job in self.container.client.job.list():
            cmd = job['cmd']
            if cmd['command'] != 'core.system':
                continue
            if cmd['arguments']['name'] == 'caddy':
                return job

    def is_running(self):
        return bool(self.get_job())