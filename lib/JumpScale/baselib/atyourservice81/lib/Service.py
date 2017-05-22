from JumpScale import j
from JumpScale.baselib.atyourservice81.lib.Recurring import RecurringTask
import asyncio

class Service:

    def __init__(self, aysrepo, loop=None):
        """
        init from a template or from a model
        """
        self.model = None
        self._schema = None
        self._path = ""
        self._loop = loop or asyncio.get_event_loop()
        self._recurring_tasks = {} # for recurring jobs

        self.aysrepo = aysrepo
        self.logger = j.logger.get('j.atyourservice.service')

    @classmethod
    async def init_from_actor(cls, aysrepo, actor, args, name):
        self = cls(aysrepo)
        try:
            await self._initFromActor(actor=actor, args=args, name=name)
            self.aysrepo.db.services.services[self.model.key] = self
            self._ensure_recurring()
            return self
        except Exception as e:
            # cleanup if init fails
            await self.delete()
            raise e

    @classmethod
    def init_from_model(cls, aysrepo, model):
        self = cls(aysrepo=aysrepo)
        self.model = model
        self.aysrepo.db.services.services[self.model.key] = self
        self._ensure_recurring()
        return self

    @classmethod
    def init_from_fs(cls, aysrepo, path):
        self = cls(aysrepo=aysrepo)
        self._loadFromFS(path)
        self.aysrepo.db.services.services[self.model.key] = self
        self._ensure_recurring()
        return self

    @property
    def name(self):
        return self.model.dbobj.name

    @property
    def path(self):
        if self._path == "":
            relpath = self.model.dbobj.gitRepo.path
            assert self.model.dbobj.gitRepo.url == self.aysrepo.git.remoteUrl
            self._path = j.sal.fs.joinPaths(self.aysrepo.path, relpath)
        return self._path

    async def _initFromActor(self, actor, name, args={}):

        self.logger.info("init service %s from %s" % (name, actor.model.name))
        if j.data.types.string.check(actor):
            raise j.exceptions.RuntimeError("no longer supported, pass actor")

        if actor is None:
            raise j.exceptions.RuntimeError("service actor cannot be None")

        self.model = self.aysrepo.db.services.new()
        dbobj = self.model.dbobj
        dbobj.name = name
        dbobj.actorName = actor.model.dbobj.name
        dbobj.actorKey = actor.model.key
        dbobj.state = "new"
        dbobj.dataSchema = actor.model.dbobj.serviceDataSchema

        skey = "%s!%s" % (self.model.role, self.model.dbobj.name)
        dbobj.gitRepo.url = self.aysrepo.git.remoteUrl
        dbobj.gitRepo.path = j.sal.fs.joinPaths("services", skey)

        # actions
        for action in actor.model.dbobj.actions:
            self.model.actionAdd(
                name=action.name,
                key=action.actionKey,
                period=action.period,
                log=action.log,
                isJob=action.isJob,
                timeout=action.timeout
            )

        # events
        events = self.model.dbobj.init_resizable_list('eventFilters')
        for event in actor.model.dbobj.eventFilters:
            eventFilter = events.add()
            eventFilter.from_dict(event.to_dict())
        events.finish()

        self.model.reSerialize()

        # set default value for argument not specified in blueprint
        template = self.aysrepo.templateGet(actor.model.name)
        msg = template.schema.new_message()
        for key, value in msg.to_dict().items():
            if key not in args:
                args[key] = value
        del(msg)  # make sure we don't hold the memory

        # input will always happen in process
        args2 = await self.input(args=args)
        if args2 is not None and j.data.types.dict.check(args2):
            args = args2

        if not j.data.types.dict.check(args):
            raise j.exceptions.Input(message="result from input needs to be dict,service:%s" % self,
                                     level=1, source="", tags="", msgpub="")

        self._valdidate_service_args(args)

        dbobj.data = j.data.capnp.getBinaryData(j.data.capnp.getObj(dbobj.dataSchema, args=args, name='Schema'))

        # parents/producers
        parent = await self._initParent(actor, args)
        if parent is not None:
            fullpath = j.sal.fs.joinPaths(parent.path, skey)
            newpath = j.sal.fs.pathRemoveDirPart(fullpath, self.aysrepo.path)
            if j.sal.fs.exists(dbobj.gitRepo.path):
                j.sal.fs.moveDir(dbobj.gitRepo.path, newpath)
            dbobj.gitRepo.path = newpath

        await self._initProducers(actor, args)

        self.save()
        self.aysrepo.db.services.services[self.model.key] = self

        await self.init()

        # need to do this manually cause execution of input method is a bit special.
        self.model.actions['input'].state = 'ok'

        self.saveAll()

    def _valdidate_service_args(self, args):
        """
        validate the arguments passed to the service during initialization to be sure we don't pass not defined arguments.
        """
        errors = []
        schema = j.data.capnp.getSchemaFromText(self.model.dbobj.dataSchema)
        for field in args:
            normalizedfieldname = j.data.hrd.sanitize_key(field)
            if normalizedfieldname not in schema.schema.fieldnames:
                errors.append('- Invalid parameter [{field}] passed while creating {service}.\n'.format(
                    field=field,
                    service="%s!%s" % (self.model.role, self.model.dbobj.name)))

        if errors:
            msg = "The arguments passed to the service %s|%s contains the following errors: \n" % (self.model.role, self.model.dbobj.name) + "\n".join(errors)
            msg += '\nDataSchema : {}'.format(self.model.dbobj.dataSchema)
            raise j.exceptions.Input(msg)

    async def _initParent(self, actor, args):
        if actor.model.dbobj.parent.actorRole is not "":
            parent_role = actor.model.dbobj.parent.actorRole

            # try to get the instance name from the args. Look for full actor name ('node.ssh') or just role (node)
            # if none of the two is available in the args, don't use instance name and
            # expect the parent service to be unique in the repo
            parent_name = args.get(actor.model.dbobj.parent.argname, args.get(parent_role, ''))
            # res = self.aysrepo.servicesFind(name=parent_name, actor='%s(\..*)?' % parent_role)
            res = self.aysrepo.servicesFind(name=parent_name, role=parent_role)
            res = [s for s in res if s.model.role == parent_role]
            if len(res) == 0:
                if actor.model.dbobj.parent.optional:
                    return None
                if actor.model.dbobj.parent.auto is False:
                    raise j.exceptions.Input(message="could not find parent:%s for %s, found 0" %
                                             (parent_name, self), level=1, source="", tags="", msgpub="")
                else:
                    auto_actor = self.aysrepo.actorGet(parent_role)
                    instance = j.data.idgenerator.generateIncrID('parent_%s' % parent_role)
                    res.append(await auto_actor.asyncServiceCreate(instance="auto_%d" % instance, args={}))
            elif len(res) > 1:
                raise j.exceptions.Input(message="could not find parent:%s for %s, found more than 1." %
                                         (parent_name, self), level=1, source="", tags="", msgpub="")
            parentobj = res[0]

            self.model.dbobj.parent.actorName = parentobj.model.dbobj.actorName
            self.model.dbobj.parent.key = parentobj.model.key
            self.model.dbobj.parent.serviceName = parentobj.name

            return parentobj

        return None

    async def _initProducers(self, actor, args):
        """
        Initialize the producers of an actor.

        actor: is the actor to init its producers.
        args: passed arguments in the blueprint (i.e {'ssh1':'main', 'sshlist':[]} )

        """
        # for every producer model in the producers, we get the user set services `argname` to be consumed in the blueprint itself.
        # calculate the difference of the available services and the user set
        # calculate the min required services and see if we should create new ones if auto is set
        # create the services required till the minServices is reached.
        # set add each to our producers and add ourself the their consumers list.
        # maintain the parent relationship (parent is always a producer and we are always a consumer of the parent.)
        for producer_model in actor.model.dbobj.producers:
            producer_role = producer_model.actorRole
            usersetservices = []
            passedservicesnames = args.get(producer_model.argname, args.get(producer_role, ""))
            if not j.data.types.list.check(passedservicesnames):
                passedservicesnames = [passedservicesnames]
            for svname in passedservicesnames:
                if svname:
                    # foundservices = self.aysrepo.servicesFind(name=svname, actor="%s(\..*)?" % producer_model.actorRole)
                    foundservices = self.aysrepo.servicesFind(name=svname, role=producer_model.actorRole)
                    usersetservices.extend(foundservices)

            available_services = self.aysrepo.servicesFind(role=producer_role)
            available_services = list(set(available_services) - set(usersetservices))

            extraservices = len(usersetservices) - producer_model.maxServices
            if extraservices > 0:
                raise j.exceptions.Input(message="Specified services [%s] are more than maximum services: [%s]" % (str(usersetservices), str(producer_model.maxServices)),
                                         level=1, source="", tags="", msgpub="")

            tocreate = producer_model.minServices - len(available_services) - len(usersetservices)
            if tocreate > 0:
                if producer_model.auto:
                    for idx in range(tocreate):
                        auto_actor = self.aysrepo.actorGet(producer_role)
                        available_services.append(await auto_actor.asyncServiceCreate(instance="auto_%s" % idx, args={}))
                else:
                    raise j.exceptions.Input(message="Minimum number of services required of role %s is %s and only %s are provided. [Hint: Maybe you want to set auto to auto create the missing services?]" % (producer_role, producer_model.minServices, len(usersetservices)),
                                             level=1, source="", tags="", msgpub="")

            for idx, producer_obj in enumerate(usersetservices + available_services):
                # if self.name == 'vdcname':
                if producer_model.auto is False and idx >= len(usersetservices) and idx >= producer_model.minServices:
                    break
                self.model.producerAdd(
                    actorName=producer_obj.model.dbobj.actorName,
                    serviceName=producer_obj.model.dbobj.name,
                    key=producer_obj.model.key)
                # add ourself to the consumers list of the producer
                producer_obj.model.consumerAdd(
                    actorName=self.model.dbobj.actorName,
                    serviceName=self.model.dbobj.name,
                    key=self.model.key)

        if self.parent is not None:
            # add parent to the producers list.
            self.model.producerAdd(
                actorName=self.parent.model.dbobj.actorName,
                serviceName=self.parent.model.dbobj.name,
                key=self.parent.model.key)

            # add ourself to the consumers list of the parent
            self.parent.model.consumerAdd(
                actorName=self.model.dbobj.actorName,
                serviceName=self.model.dbobj.name,
                key=self.model.key)

        self.model.reSerialize()

    def _check_args(self, actor, args):
        """ Checks whether if args are the same as in instance model """
        data = j.data.serializer.json.loads(self.model.dataJSON)
        for key, value in args.items():
            sanitized_key = j.data.hrd.sanitize_key(key)
            if sanitized_key in data and data[sanitized_key] != value or sanitized_key not in data:
                self.processChange(actor=actor, changeCategory="dataschema", args=args)
                break

    def _loadFromFS(self, path):
        """
        get content from fs and load in object
        only for DR purposes, std from key value stor
        """
        self.logger.debug("load service from FS: %s" % path)
        if self.model is None:
            self.model = self.aysrepo.db.services.new()

        model_json = j.data.serializer.json.load(j.sal.fs.joinPaths(path, "service.json"))
        self.model.key = model_json.pop('key')

        self.model.dbobj = self.model.collection.capnp_schema.new_message(**model_json)

        data_json = j.data.serializer.json.load(j.sal.fs.joinPaths(path, "data.json"))
        self.model.dbobj.data = j.data.capnp.getBinaryData(
            j.data.capnp.getObj(self.model.dbobj.dataSchema, args=data_json))

        # relink actions from the actor to be sure we have good keys
        actor = self.aysrepo.actorGet(name=self.model.dbobj.actorName)

        for actor_action in actor.model.dbobj.actions:
            # search correct action in actor model
            if actor_action.name in self.model.actions:
                self.model.actions[actor_action.name].actionKey = actor_action.actionKey

        self.saveAll()

    def saveToFS(self):
        j.sal.fs.createDir(self.path)
        path2 = j.sal.fs.joinPaths(self.path, "service.json")
        j.sal.fs.writeFile(path2, self.model.dictJson, append=False)

        path3 = j.sal.fs.joinPaths(self.path, "data.json")
        j.sal.fs.writeFile(path3, self.model.dataJSON)

        path4 = j.sal.fs.joinPaths(self.path, "schema.capnp")
        j.sal.fs.writeFile(path4, self.model.dbobj.dataSchema)

    def save(self):
        self.model.save()

    def saveAll(self):
        self.model.save()
        self.saveToFS()

    def reload(self):
        # service are kept in memory so we never need to relad anyomre
        pass

    async def delete(self):
        """
        delete this service completly.
        remove it from db and from filesystem
        all the children of this service are going to be deleted too
        """
        # TODO should probably warn user relation may be broken

        for service in self.children:
            await service.delete()

        # cancel all recurring tasks
        self.stop()

        for producers in self.producers.values():
            for producer in producers:
                producer.model.consumerRemove(self)
                producer.model.reSerialize()
                producer.saveAll()

        for consumers in self.consumers.values():
            for consumer in consumers:
                consumer.model.producerRemove(self)
                consumer.model.reSerialize()
                consumer.saveAll()

        self.model.delete()
        j.sal.fs.removeDirTree(self.path)
        if self.model.key in self.aysrepo.db.services.services:
            del self.aysrepo.db.services.services[self.model.key]

    @property
    def parent(self):
        self.model.reSerialize()
        if self.model.parent is not None:
            return self.model.parent.objectGet(self.aysrepo)
        return None

    @property
    def parents(self):
        chain = []
        parent = self.parent
        while parent is not None:
            chain.append(parent)
            parent = parent.parent
        return chain

    @property
    def children(self):
        res = []
        for service in self.aysrepo.services:
            if service.parent == self:
                res.append(service)
        return res

    @property
    def producers(self):
        self.model.reSerialize()
        producers = {}
        for prod in self.model.dbobj.producers:
            role = prod.actorName.split(".")[0]
            if role not in producers:
                producers[role] = []
            producers[role].append(self.aysrepo.serviceGet(key=prod.key))
        return producers

    @property
    def consumers(self):
        self.model.reSerialize()
        consumers = {}
        for cons in self.model.dbobj.consumers:
            role = cons.actorName.split(".")[0]
            if role not in consumers:
                consumers[role] = []
            consumers[role].append(self.aysrepo.serviceGet(key=cons.key))
        return consumers

    def isConsumedBy(self, service):
        consumers_keys = [model.key for model in self.model.consumers]
        return service.model.key in consumers_keys

    def findConsumersRecursive(self, target=None, out=set()):
        """
        @return set of services that consumes target, recursivlely
        """
        if target is None:
            target = self
        for service in target.consumers:
            out.add(service)
            self.findConsumersRecursive(service, out)
        return out

    def getProducersRecursive(self, producers=set(), callers=set(), action="", producerRoles="*"):
        for role, producers_list in self.producers.items():
            for producer in producers_list:
                if action == "" or action in producer.model.actionsState.keys():
                    if producerRoles == "*" or producer.model.role in producerRoles:
                        producers.add(producer)
                producers = producer.getProducersRecursive(
                    producers=producers, callers=callers, action=action, producerRoles=producerRoles)
        return producers.symmetric_difference(callers)

    def printProducersRecursive(self, prefix=""):
        for role, producers2 in self.producers.items():
            # print ("%s%s"%(prefix,role))
            for producer in producers2:
                print("%s- %s" % (prefix, producer))
                producer.printProducersRecursive(prefix + "  ")

    def getConsumersRecursive(self, consumers=set(), callers=set(), action="", consumerRole="*"):
        for role, consumers_list in self.consumers.items():
            for consumer in consumers_list:
                if action == "" or action in consumer.model.actionsState.keys():
                    if consumerRole == "*" or consumer.model.role in consumerRole:
                        consumers.add(consumer)
                consumers = consumer.getConsumersRecursive(
                    consumers=consumers, callers=callers, action=action, consumerRole=consumerRole)
        return consumers.symmetric_difference(callers)

    def getConsumersWaiting(self, action='uninstall', consumersChanged=set(), scope=None):
        for consumer in self.getConsumersRecursive(set(), set()):
            # check that the action exists, no need to wait for other actions,
            # appart from when init or install not done

            if consumer.model.actionsState['init'] != "ok":
                consumersChanged.add(consumer)

            if consumer.model.actionsState['install'] != "ok":
                consumersChanged.add(consumer)

            if action not in consumer.model.actionsState.keys():
                continue

            if consumer.model.actionsState[action] != "ok":
                consumersChanged.add(consumer)

        if scope is not None:
            consumersChanged = consumersChanged.intersection(scope)

        return consumersChanged

    def consume(self, service):
        """
        consume another service dynamicly
        """
        if service.model.role in self.producers and service in self.producers[service.model.role]:
            return

        self.model.producerAdd(
            actorName=service.model.dbobj.actorName,
            serviceName=service.name,
            key=service.model.key)

        # add ourself to the consumers list of the producer
        service.model.consumerAdd(
            actorName=self.model.dbobj.actorName,
            serviceName=self.model.dbobj.name,
            key=self.model.key)

        self.model.reSerialize()
        service.model.reSerialize()

        self.saveAll()
        service.saveAll()

    @property
    def executor(self):
        return self._getExecutor()

    def _getExecutor(self):
        executor = None
        tocheck = [self]
        tocheck.extend(self.parents)
        for service in tocheck:
            if 'getExecutor' in service.model.actionsState.keys():
                job = service.getJob('getExecutor')
                executor = job.method(job)
                return executor
        return j.tools.executor.getLocal()

    def processChange(self, actor, changeCategory, args={}, reschedule=False):
        """
        template action change
        categories :
            - dataschema
            - ui
            - config
            - action_new_actionname
            - action_mod_actionname
        """
        # TODO: implement different pre-define action for each category
        # self.logger.debug('process change for %s (%s)' % (self, changeCategory)

        if changeCategory == 'dataschema':
            # We use the args passed without change
            pass

        elif changeCategory == 'ui':
            # TODO
            pass
        elif changeCategory == 'config':
            # update the recurrin and event actions
            # then set the lastrun to the value it was before update
            recurring_lastrun = {}
            event_lastrun = {}

            for event in self.model.actionsEvent.values():
                event_lastrun[event.action] = event.lastRun
            for recurring in self.model.actionsRecurring.values():
                recurring_lastrun[recurring.action] = recurring.lastRun

            self._initRecurringActions(actor)
            self._initEventActions(actor)

            for action, lastRun in event_lastrun.items():
                self.model.actionsEvent[action].lastRun = lastRun
            for action, lastRun in recurring_lastrun.items():
                self.model.actionsRecurring[action].lastRun = lastRun

        elif changeCategory.find('action_new') != -1:
            action_name = changeCategory.split('action_new_')[1]
            actor_action_pointer = actor.model.actions[action_name]
            self.model.actionAdd(key=actor_action_pointer.actionKey, name=action_name)

        elif changeCategory.find('action_mod') != -1:
            # update state and pointer of the action pointer in service model
            action_name = changeCategory.split('action_mod_')[1]
            action_actor_pointer = actor.model.actions[action_name]
            service_action_pointer = self.model.actions[action_name]
            if service_action_pointer.state == 'error' and not reschedule:
                service_action_pointer.state = 'changed'
            service_action_pointer.actionKey = action_actor_pointer.actionKey

            # update the lastModDate of the action object
            action = j.core.jobcontroller.db.actions.get(key=service_action_pointer.actionKey)
            action.dbobj.lastModDate = j.data.time.epoch
            action.save()

        elif changeCategory.find('action_del') != -1:
            action_name = action_name = changeCategory.split('action_del_')[1]
            self.model.actionDelete(action_name)

        # save the change for the service
        self.saveAll()

        # execute the processChange method if it exists
        if 'processChange' in self.model.actions.keys():
            args.update({'changeCategory': changeCategory})
            job = self.getJob("processChange", args=args)
            args = job.executeInProcess()
            job.model.save()

    async def processEvent(self, channel=None, command=None, secret=None, tags={}, payload=None):
        coros = []
        for event_filter in self.model.dbobj.eventFilters:
            if channel is not None and channel != 'all' and channel != event_filter.channel:
                continue
            if command is not None and command != event_filter.command:
                continue
            if secret is not None and secret != event_filter.secret:
                continue
            # TODO: tags ??

            for action in event_filter.actions:
                self.logger.info("create event job for {}:{}".format(self, action))
                # in the case of webhook, we also pass the requet object to the model
                # so action can investigate the original request that triggers the even
                if 'request' in payload:
                    request = payload.pop('request')
                job = self.getJob(action, args=payload)
                job.model.request = request

                coros.append(job.execute())

        if len(coros) <= 0:
            return

        self.logger.debug("wait for all event jobs to complete")
        await asyncio.gather(*coros)

    async def input(self, args={}):
        job = self.getJob("input", args=args)
        job._service = self
        job.saveService = False  # this is done to make sure we don't save the service at this point !!!
        args = await job.executeInProcess()
        job.model.actorName = self.model.dbobj.actorName
        job.model.save()
        return args

    async def init(self):
        job = self.getJob(actionName="init")
        await job.executeInProcess()
        job.model.save()
        return job

    def checkActions(self, actions):
        """
        will walk over all actions, and make sure the default are well set.

        """
        from IPython import embed
        print("DEBUG NOW checkactions")
        embed()
        raise RuntimeError("stop debug here")

    def scheduleAction(self, action, args={}, period=None, log=True, force=False):
        """
        Change the state of an action so it marked as need to be executed
        if the period is specified, also create a recurring period for the action
        """
        if action not in self.model.actions:
            self.logger.warning("Trying to schedule action %s on %s. but this action doesn't exist" % (action, self))
            return

        action_model = self.model.actions[action]

        if action_model.state == 'disabled':
            raise j.exceptions.Input("Trying to schedule action %s on %s. but this action is disabled" % (action, self))

        if period is not None and period != '':
            # convert period to seconds
            if j.data.types.string.check(period):
                period = j.data.types.duration.convertToSeconds(period)
            elif j.data.types.int.check(period) or j.data.types.float.check(period):
                period = int(period)
            # save period into actionCode model
            action_model.period = period
            self._ensure_recurring()


        if not force and action_model.state == 'ok':
            self.logger.info("action %s already in ok state, don't schedule again" % action_model.name)
        else:
            self.logger.info('schedule action %s on %s' % (action, self))
            action_model.state = 'scheduled'

        self.saveAll()

    async def executeAction(self, action, args={}):
        if action[-1] == "_":
            return self.executeActionService(action)
        else:
            return await self.executeActionJob(action, args)

    def executeActionService(self, action, args={}):
        # execute an action in process without creating a job
        # usefull for methods called very often.
        action_id = self.model.actions[action].actionKey
        action_model = j.core.jobcontroller.db.actions.get(action_id)
        action_with_lines = ("\n%s \n" % action_model.code)
        indented_action = '\n    '.join(action_with_lines.splitlines())
        complete_action = "def %s(%s): %s" % (action, action_model.argsText, indented_action)
        exec(complete_action)
        res = eval(action)(service=self, args=args)
        return res

    async def executeActionJob(self, actionName, args={}):
        """
        creates a job and execute the action names actionName
        @param actionName: name of the action to execute
        @actionName type: string
        @param args: arguments to pass to the action
        @args type: dict
        @return: result of the action.
        """
        job = self.getJob(actionName=actionName, args=args)

        result = await job.execute()
        if isinstance(result, tuple) and len(result) == 3:
            return result[0]
        else:
            return result

    def getJob(self, actionName, args={}):
        action = self.model.actions[actionName]
        jobobj = j.core.jobcontroller.db.jobs.new()
        jobobj.dbobj.repoKey = self.aysrepo.path
        jobobj.dbobj.actionKey = action.actionKey
        jobobj.dbobj.actionName = action.name
        jobobj.dbobj.actorName = self.model.dbobj.actorName
        jobobj.dbobj.serviceName = self.model.dbobj.name
        jobobj.dbobj.serviceKey = self.model.key
        jobobj.dbobj.state = "new"
        jobobj.dbobj.lastModDate = j.data.time.epoch
        jobobj.args = args
        job = j.core.jobcontroller.newJobFromModel(jobobj)
        job.service = self
        return job

    def _build_actions_chain(self, action, ds=list(), parents=list(), dc=None):
        """
        this method returns a list of action that need to happens before the action passed in argument
        can start
        """
        if dc is None:
            dependency_chain = self.executeActionService('init_actions_', args={'action': action})
        if action in parents:
            raise RuntimeError('cyclic dep: %s' % parents)
        if action in ds:
            return
        ds.append(action)
        newkeys = dependency_chain.get(action)
        if not newkeys:
            return
        parents.append(action)
        for key in newkeys:
            self._build_actions_chain(key, ds, parents, dc)
        parents.pop()
        return

    def _ensure_recurring(self):
        """
        this method is added to the event loop after service creation
        it makes sure all the recurrung action of the services are created and running
        """
        for action, info in self.model.actionsRecurring.items():
            if action not in self._recurring_tasks:
                # creates new tasks
                task = RecurringTask(service=self, action=action, period=info.period, loop=self.aysrepo._loop)
                task.start()
                self._recurring_tasks[action] = task
                # make sure that the loop used for recurring is the main loop.
                # this is needed in case the service is create within another service
                # in this case the service creation runs in a thread, thus we need to pass the correct loop
                assert task._loop == self.aysrepo._loop

            else:
                # task already exists, make sure the period is correct
                # and the task is running
                task = self._recurring_tasks[action]
                if info.period != task.period:
                    task.period = info.period
                if not task.started:
                    task.start()

        # stop recurring tasks that doesn't exists anymore
        needed = set(self.model.actionsRecurring.keys())
        actual = set(self._recurring_tasks.keys())
        for name in actual.difference(needed):
            task = self._recurring_tasks[name]
            task.stop()
            del self._recurring_tasks[name]

    def stop(self):
        """
        stop all recurring action of the services
        """
        # cancel all recurring tasks
        for k in list(self._recurring_tasks.keys()):
            self._recurring_tasks[k].stop()
            del self._recurring_tasks[k]

    def __eq__(self, service):
        if not service:
            return False
        return service.model.key == self.model.key

    def __hash__(self):
        return hash(self.model.key)

    def __repr__(self):
        return "service:%s!%s" % (self.model.role, self.model.dbobj.name)

    def __str__(self):
        return self.__repr__()

    def _getDisabledProducers(self):
        disabled = []
        for producers_list in self.producers.values():
            for producer in producers_list:
                if producer.model.dbobj.state == 'disabled':
                    disabled.append(producer)
        return disabled

    # def disable(self):
    #     for consumer in self.getConsumers():
    #         candidates = self.aysrepo.findServices(role=self.model.role, first=False)
    #         if len(candidates) > 1:
    #             # Other candidates available. Should link consumer to new
    #             # candidate
    #             candidates.remove(self)
    #             candidate = candidates[0]
    #             producers = consumer.hrd.getList('producer.%s' % self.role, [])
    #             producers.remove(self.key)
    #             producers.append(candidate.key)
    #             consumer.hrd.set('producer.%s' % self.role, producers)
    #         else:
    #             # No other candidates already installed. Disable consumer as
    #             # well.
    #             consumer.disable()
    #
    #     self.logger.info("disable instance")
    #     self.model.hrd.set('disabled', True)
    #
    # def _canBeEnabled(self):
    #     for role, producers in list(self.producers.items()):
    #         for producer in producers:
    #             if producer.state.hrd.getBool('disabled', False):
    #                 return False
    #     return True
    #
    # def enable(self):
    #     # Check that all dependencies are enabled
    #
    #     if not self._canBeEnabled():
    #         self.logger.info(
    #             "%s cannot be enabled because one or more of its producers is disabled" % self)
    #         return
    #
    #     self.model.hrd.set('disabled', False)
    #     self.logger.info("Enable instance")
    #     for consumer in self._getConsumers(include_disabled=True):
    #         consumer.enable()
    #         consumer.start()
    #
