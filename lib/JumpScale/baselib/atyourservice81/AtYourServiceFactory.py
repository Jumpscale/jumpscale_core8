from JumpScale import j

from JumpScale.baselib.atyourservice81.lib.TemplateRepo import TemplateRepoCollection
from JumpScale.baselib.atyourservice81.lib.ActorTemplate import ActorTemplate
from JumpScale.baselib.atyourservice81.lib import ActionsBase
from JumpScale.baselib.atyourservice81.lib.AtYourServiceRepo import AtYourServiceRepo, AtYourServiceRepoCollection
from JumpScale.baselib.atyourservice81.lib.AtYourServiceTester import AtYourServiceTester

import colored_traceback
import os
import sys
import inotify.adapters
import threading
if "." not in sys.path:
    sys.path.append(".")

import inspect
import asyncio

colored_traceback.add_hook(always=True)


class AYSNotify(inotify.adapters.InotifyTrees):

    def event_gen(self):
        """This is a secondary generator that wraps the principal one, and
        adds/removes watches as directories are added/removed.
        """

        for event in self._i.event_gen():
            if event is not None:
                (header, type_names, path, filename) = event

                if header.mask & inotify.constants.IN_ISDIR:
                    full_path = os.path.join(path, filename)

                    if header.mask & inotify.constants.IN_CREATE:
                        if not any(filename.startswith(i.encode()) for i in '._'):
                            self._i.add_watch(full_path, self._mask)
                    elif header.mask & inotify.constants.IN_DELETE:
                        self._i.remove_watch(full_path, superficial=True)

            yield event

    def __load_trees(self, paths):

        q = paths
        while q:
            current_path = q[0]
            del q[0]

            if any(current_path.startswith(i.encode()) for i in '._'):
                continue

            self._i.add_watch(current_path, self._mask)

            for filename in os.listdir(current_path):
                entry_filepath = os.path.join(current_path, filename)
                if os.path.isdir(entry_filepath) is False:
                    continue

                q.append(entry_filepath)

class AtYourServiceFactory:

    def __init__(self):
        self.__jslocation__ = "j.atyourservice"
        self.loop = None
        self._config = None
        self._domains = []
        self.debug = j.core.db.get("atyourservice.debug") == 1
        self.dev_mode = False
        self.logger = j.logger.get('j.atyourservice')
        self.started = False

        self.baseActions = {}
        self.templateRepos = None
        self.aysRepos = None
        self._cleanupHandle = None

    def start(self, bind='127.0.0.1', port=5000, log='info'):
        """
        start an ays service on your local platform
        """
        try:
            sname = j.tools.cuisine.local.tmux.getSessions()[0]
        except:
            sname = "main"

        cmd = "cd /opt/code/github/jumpscale/jumpscale_core8/apps/atyourservice; \
              jspython main.py --host {host} --port {port} --log {log}".format(
            host=bind, port=port, log=log)
        print("Starting AtYourService server in a tmux session")
        rc, out = j.tools.cuisine.local.tmux.executeInScreen(sname, "ays", cmd, reset=True, wait=5)
        if rc > 0:
            raise RuntimeError("Cannot start AYS service")

        if log == 'debug':
            print("debug logging enabled")
        print("AYS server running at http://{}:{}".format(bind, port))
        return rc, out

    def cleanup(self):
        sleep = 60
        runs = j.core.jobcontroller.db.runs.find()
        limit = int(j.data.time.getEpochAgo("-2h"))
        for run in runs:
            if run.dbobj.state in ['error', 'ok']:
                j.core.jobcontroller.db.runs.delete(state=run.dbobj.state, repo=run.dbobj.repo, toEpoch=limit)
        jobs = j.core.jobcontroller.db.jobs.find()
        for job in jobs:
            if job is None:
                continue

            elif job.state in ['error', 'ok']:
                j.core.jobcontroller.db.jobs.delete(actor=job.dbobj.actorName, service=job.dbobj.serviceName,
                                                    action=job.dbobj.actionName, state=job.state,
                                                    serviceKey=job.dbobj.serviceKey, toEpoch=limit)
                del job
        self._cleanupHandle = self.loop.call_later(sleep, self.cleanup)

    def _start(self, loop=None):
        self.loop = loop or asyncio.get_event_loop()
        self.templateRepos = TemplateRepoCollection()  # actor templates repositories
        self.aysRepos = AtYourServiceRepoCollection()  # ays repositories
        self.started = True
        t = threading.Thread(target=self._watch_repos)
        t.start()
        if not self._cleanupHandle:
            self._cleanupHandle = self.loop.call_soon(self.cleanup)

    def _watch_repos(self):
        with open('/proc/sys/fs/inotify/max_user_watches') as f:
            num = f.read().strip()
        error_message = """Inotify Error
------------------ ERROR ------------------
Inotify returned an error, it probably happened because of the inotify limit of the system which is {}
you can increase this value using:
echo <the new value> > /proc/sys/fs/inotify/max_user_watches
-------------------------------------------""".format(num)
        try:
            mask = inotify.constants.IN_MOVE | inotify.constants.IN_CREATE | inotify.constants.IN_DELETE
            i = AYSNotify([d.encode() for d in [j.dirs.VARDIR, j.dirs.CODEDIR]], mask=mask)
        except inotify.calls.InotifyError as e:
                self.logger.warn("inotify error %s" % e)
                self.logger.error(error_message)
                # TODO: fall back to reloading every 60 seconds
                raise

        self.logger.info("Watching repos for changes")

        while self.started:
            try:
                for event in i.event_gen():
                    if not self.started:
                        return
                    if event is not None:
                        (header, type_names, dirname, filename) = event
                        for repos in [self.aysRepos, self.templateRepos]:
                            try:
                                if any(dirname.decode().startswith(d) for d in repos.FSDIRS):
                                    repos.handle_fs_events(dirname.decode(), filename.decode(), event)
                            except Exception as e:
                                print(e)
                else:
                    break
            except inotify.calls.InotifyError as e:
                self.logger.warn("inotify error %s" % e)
                self.logger.error(error_message)

    async def _stop(self):
        self.logger.info("stopping AtYourService")
        self.started = False
        to_wait = [repo.stop() for repo in self.aysRepos.list()]
        self.loop.run_until_complete(asyncio.gather(*to_wait))
        self.loop.close()

    @property
    def actorTemplates(self):
        templates = []
        for template_repo in self.templateRepos.list():
            if template_repo.is_global:
                templates.extend(template_repo.templates)
        return templates

    @property
    def config(self):
        if self._config is None:
            cfg = j.application.config.jumpscale.get('ays')
            if not cfg:
                cfg = {}
            if 'redis' not in cfg:
                cfg.update({'redis': j.core.db.config_get('unixsocket')})
            self._config = cfg
        return self._config

    def _upgradeTemplate2yaml(self, actors_paths=[]):
        """
        upgrade actor templates from hrd version to yaml version
        """
        path = j.sal.fs.pathNormalize(j.dirs.CODEDIR)

        # check if this is already an actortemplate dir, if not no need to recurse
        def isValidTemplate(path):
            dirname = j.sal.fs.getBaseName(path)
            tocheck = ['schema.hrd']
            if dirname.startswith("_") or dirname.startswith("."):
                return False
            for aysfile in tocheck:
                if j.sal.fs.exists('%s/%s' % (path, aysfile)):
                    if not dirname.startswith("_"):
                        return True
                    else:
                        return False
            return False

        def callbackFunctionDir(path, arg):
            # print(path)
            # base = j.sal.fs.getBaseName(path)
            if arg[3] != "" and isValidTemplate(path):
                # print(path)
                arg[1].append(path)

        def callbackForMatchDir(path, arg):
            base = j.sal.fs.getBaseName(path)
            if base.startswith("."):
                return False
            # if base in [".git", ".hg", ".github"]:
            #     return False
            if base.startswith("ays_"):
                arg[2] = path
            elif arg[2] != "":
                if not path.startswith(arg[2]):
                    arg[2] = ""
                    # because means that ays repo is no longer our parent

            if base == "templates" and arg[2] != "":
                arg[3] = path
            elif arg[3] != "":
                if not path.startswith(arg[3]):
                    arg[3] = ""
                    # because means that  is no longer our parent

            depth = len(j.sal.fs.pathRemoveDirPart(path, arg[0]).split("/"))
            # print("%s:%s" % (depth, j.sal.fs.pathRemoveDirPart(path, arg[0])))
            if depth < 4:
                return True
            elif depth < 8 and arg[3] != "":
                return True
            return False

        def sanitize_key(key):
            """
            make sure the key of an HRD schema has a valid format for Capnp Schema
            e.g.:
                ssh.port becomes sshPort
            """
            separator = ['_', '.']
            for sep in separator:
                if key.find(sep) != -1:
                    ss = key.split(sep)
                    key = ss[0]
                    for s in ss[1:]:
                        key += s[0].upper()
                        if len(s) > 1:
                            key += s[1:]
            return key

        if actors_paths == []:
            j.sal.fswalker.walkFunctional(path, callbackFunctionFile=None, callbackFunctionDir=callbackFunctionDir, arg=[path, actors_paths, "", ""],
                                          callbackForMatchDir=callbackForMatchDir, callbackForMatchFile=lambda x, y: False)

        for ppath in actors_paths:
            print("upgrade:%s" % ppath)
            schema = j.data.hrd.getSchema(path=ppath + "/schema.hrd")
            actor = j.data.hrd.get(path=ppath + "/actor.hrd")
            if schema != None:
                j.sal.fs.writeFile(ppath + "/schema.capnp", schema.capnpSchema)

            schemaParent = schema.parentSchemaItemGet()
            schemaConsume = schema.consumeSchemaItemsGet()
            output = {}

            if schemaParent != None or schemaConsume != []:
                output['links'] = {}

            if schemaParent != None:
                output['links'] = {'parent': {
                    'role':  sanitize_key(schemaParent.parent),
                    'auto': bool(schemaParent.auto),
                    'optional': bool(schemaParent.optional)
                }}

            if schemaConsume != []:
                output['links']['consume'] = []

                for item in schemaConsume:
                    output['links']['consume'].append({
                        'role':  item.consume_link,
                        'argname': sanitize_key(item.name),
                        'auto': bool(item.auto),
                        'min': item.consume_nr_min,
                        'max': item.consume_nr_max
                    })

            docs = [(item[0], item[1].description) for item in schema.items.items()]
            if docs != []:
                output['doc'] = {'property': []}

            for key, doc in docs:
                output['doc']['property'].append({
                    sanitize_key(key): doc
                })

            output['recurring'] = []
            for action_name, info in actor.getDictFromPrefix('recurring').items():
                output['recurring'].append({
                    'action': action_name,
                    'log': j.data.types.bool.fromString(info['log']),
                    'period': info['period']
                })

            j.data.serializer.yaml.dump(j.sal.fs.joinPaths(ppath, 'config.yaml'), output)
            j.sal.fs.remove(ppath + "/schema.hrd")
            j.sal.fs.remove(ppath + "/actor.hrd")

    def reset(self):
        self._domains = []
        self.baseActions = {}
        self.templateRepos = None
        self.aysRepos = None
        self._start(loop=self.loop)

    def getAYSTester(self, name="fake_IT_env"):
        self._init()
        return AtYourServiceTester(name)

    def _loadActionBase(self):
        """
        load all the basic actions for atyourservice
        """
        if self.baseActions == {}:
            for method in [item[1] for item in inspect.getmembers(ActionsBase) if item[0][0] != "_"]:
                action_code_model = j.core.jobcontroller.getActionObjFromMethod(method)
                if not j.core.jobcontroller.db.actions.exists(action_code_model.key):
                    # will save in DB
                    action_code_model.save()
                self.baseActions[action_code_model.dbobj.name] = action_code_model, method
