from JumpScale import j
from Base import Base


class User(Base):

    def __init__(self, client, githubObj=None):
        self.logger = j.logger.get('j.clients.github.user')
        self._ddict = {}
        self._githubObj = githubObj
        if githubObj is not None:
            self.load()

    @property
    def api(self):
        if self._githubObj is None:
            from IPython import embed
            print("DEBUG NOW get api for user")
            embed()
        return self._githubObj

    def load(self):
        self._ddict = {}
        self._ddict["name"] = self.api.name
        self._ddict["email"] = self.api.email
        self._ddict["id"] = self.api.id
        self._ddict["login"] = self.api.login

    @property
    def name(self):
        return self._ddict["name"]

    @property
    def email(self):
        return self._ddict["email"]

    @property
    def id(self):
        return self._ddict["id"]

    @property
    def login(self):
        return self._ddict["login"]