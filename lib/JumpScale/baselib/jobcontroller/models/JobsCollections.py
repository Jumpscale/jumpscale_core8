from JumpScale import j
from JumpScale.baselib.jobcontroller.models.JobModel import JobModel

import capnp
from JumpScale.baselib.jobcontroller import model_job_capnp as ModelCapnp
from JumpScale.data.capnp.ModelBase import ModelBaseCollection



class JobsCollection(ModelBaseCollection):
    """
    This class represent a collection of Jobs
    It's used to list/find/create new Instance of Job Model object
    """

    def __init__(self):
        self.logger = j.logger.get('j.jobcontroller.job-collection')
        self.namespace_prefix = 'jobs'
        category = 'Job'
        namespace = "%s:%s" % (self.namespace_prefix, category.lower())
        db = j.servers.kvs.getRedisStore(namespace, namespace, **j.atyourservice.config['redis'])
        super().__init__(ModelCapnp.Job, category=category, namespace=namespace, modelBaseClass=JobModel, db=db, indexDb=db)

    def new(self):
        model = JobModel(
            key='',
            new=True,
            collection=self)
        return model

    def get(self, key):
        if not self.exists(key):
            return
        return JobModel(
            key=key,
            new=False,
            collection=self)

    def exists(self, key):
        return self._db.exists(key)

    def list(self, actor="", service="", action="", state="", serviceKey="", fromEpoch=0, toEpoch=9999999999999, returnIndex=False):
        if actor == "":
            actor = ".*"
        if service == "":
            service = ".*"
        if action == "":
            action = ".*"
        if state == "":
            state = ".*"
        if serviceKey == "":
            serviceKey = ".*"
        epoch = ".*"
        regex = "%s:%s:%s:%s:%s:%s" % (actor, service, action, state, serviceKey, epoch)
        res0 = self._index.list(regex, returnIndex=True)
        res1 = []
        for index, key in res0:
            epoch = int(index.split(":")[-1])
            if fromEpoch <= epoch and epoch < toEpoch:
                if returnIndex:
                    res1.append((index, key))
                else:
                    res1.append(key)
        return res1

    def find(self, actor="", service="", action="", state="", serviceKey="", fromEpoch=0, toEpoch=9999999999999):
        res = []
        for key in self.list(actor, service, action, state, serviceKey, fromEpoch, toEpoch):
            res.append(self.get(key))
        return res


    def getIndexFromKey(self, key):
        job = self.get(key)
        ind = "%s:%s:%s:%s:%s:%s" % (job.dbobj.actorName, job.dbobj.serviceName,
                                     job.dbobj.actionName, job.dbobj.state, job.dbobj.serviceKey, job.dbobj.lastModDate)
        return ind

    def destroy(self):
        self._db.destroy()
        self._index.destroy()
