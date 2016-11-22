from JumpScale import j


app = j.tools.cuisine._getBaseAppClass()


class CuisineAysBot(app):
    NAME = ''

    def isInstalled(self):
        return self._cuisine.core.file_exists(
            "$appDir/ays_bot/telegram-bot") and self._cuisine.core.file_exists('$cfgDir/ays_bot/config.toml')

    def __init__(self, executor, cuisine):
        self._cuisine = cuisine
        self.executor = executor
        self._configured = False

    def install(self, start=True, link=True, reset=False):
        """
        please configure first
        Install aysbot
        If start is True, token g8_addresses, dns and oauth should be specified
        """
        if not reset and self.isInstalled():
            return

        self._cuisine.bash.environSet("LC_ALL", "C.UTF-8")
        if not self._cuisine.core.isMac and not self._cuisine.core.isCygwin:
            self._cuisine.development.js8.install()
            self._cuisine.development.pip.packageUpgrade("pip")

        self.install_deps()
        self._cuisine.development.git.pullRepo('https://github.com/Jumpscale/jscockpit.git')
        if link:
            self.link_code()
        else:
            self.copy_code()

        if start:
            self.start()

    def start(self, token=None, host="0.0.0.0", port=6366, itsyouonlinehost="https://itsyou.online",
              dns=None, client_id=None, client_secret=None, cfg=None):
        """
        token: telegram bot token received from @botfather
        oauth: dict containing
               host
               oauth
               client_id
               client_secret
               itsyouonline.host
        cfg: full dict with config optional
        """
        import ipdb; ipdb.set_trace()
        if not self._configured:
            self.create_config(token, host, port, itsyouonlinehost, dns, client_id, client_secret, cfg)
        cmd = self._cuisine.core.args_replace(
            'jspython ays-bot.py --config $cfgDir/ays_bot/config.toml')
        cwd = self._cuisine.core.args_replace('$appDir/ays_bot')
        self._cuisine.processmanager.ensure('aysbot', cmd=cmd, path=cwd)

    def install_deps(self):
        deps = """
        flask
        python-telegram-bot
        """
        self._cuisine.development.pip.multiInstall(deps, upgrade=True)

    def link_code(self):
        self._cuisine.core.dir_ensure("$appDir")
        self._cuisine.core.file_link('$codeDir/github/jumpscale/jscockpit/ays_bot/', '$appDir/ays_bot')

    def copy_code(self):
        self._cuisine.core.dir_ensure("$appDir")
        self._cuisine.core.file_copy('$codeDir/github/jumpscale/jscockpit/ays_bot/', '$appDir/', recursive=True)

    def create_config(self, token=None, host="0.0.0.0", port=6366, itsyouonlinehost="https://itsyou.online",
                      dns=None, client_id=None, client_secret=None, cfg=None):
        """
        token: telegram bot token received from @botfather
        dns: str dns key path
        oauth: dict containing
               host
               oauth
               client_id
               client_secret
               itsyouonline.host
        cfg: dict with config optional
        """
        self._configured = True
        if not cfg:
            redirect = "http://%s/callback" % dns
            if not dns:
                redirect = "http://%s:%s/callback" % (host, port)

            cfg = {'token': token,
                   'oauth': {
                       'host': host,
                       'port': port,
                       'organization': client_id,
                       'client_id': client_id,
                       'client_secret': client_secret,
                       'redirect_uri': redirect,
                       'itsyouonlinehost': itsyouonlinehost
                       }
                   }

        config = j.data.serializer.toml.dumps(cfg)
        self._cuisine.core.dir_ensure("$cfgDir/ays_bot")
        self._cuisine.core.file_write("$cfgDir/ays_bot/config.toml", config)
