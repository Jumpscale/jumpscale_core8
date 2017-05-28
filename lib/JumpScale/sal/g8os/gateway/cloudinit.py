import time


class CloudInit:
    def __init__(self, container, config):
        self.container = container
        self.config = config
        self.CONFIGPATH = "/etc/cloud-init"

    def apply_config(self):
        self.cleanup(self.config.keys())

        for key, value in self.config.items():
            fpath = "%s/%s" % (self.CONFIGPATH, key)
            self.container.upload_content(fpath, value)

    def cleanup(self, macaddresses):
        configs = self.container.client.filesystem.list(self.CONFIGPATH)
        for config in configs:
            if config["name"] not in macaddresses:
                self.container.client.filesystem.remove("%s/%s" % (self.CONFIGPATH, config["name"]))

    def start(self):
        if not self.is_running():
            self.container.client.system(
                'cloud-init-server \
                -bind 127.0.0.1:8080 \
                -config {config}'
                .format(config=self.CONFIGPATH)
            )

        # TODO: Check with Core0 team if listing ports can be available to check success
        time.sleep(2)
        if not self.is_running():
            raise RuntimeError('Failed to start cloudinit server')

    def is_running(self):
        for job in self.container.client.job.list():
            if job["cmd"]["arguments"].get("name") == "cloud-init-server":
                return True
        return False
