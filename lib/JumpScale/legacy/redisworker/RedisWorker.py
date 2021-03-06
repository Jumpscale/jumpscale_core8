from JumpScale import j

try:
    import ujson as json
except:
    import json

import time
import inspect

Jumpscript = j.legacy.jumpscripts.getJSClass()


class Job(object):
    """
    identifies a job in the grid
    """

    def __init__(self, ddict={}, args={}, timeout=60, sessionid=None, jscriptid=None, cmd="", category="", log=True,
                 queue=None, wait=False, internal=False):
        self.errorreport = False
        self.internal = False
        if ddict != {}:
            self.load(ddict)
        else:
            self.id = 0
            self.sessionid = sessionid
            self.gid = j.application.whoAmI.gid
            self.nid = j.application.whoAmI.nid
            self.cmd = cmd
            self.wait = wait
            self.category = category
            self.jscriptid = jscriptid
            self.roles = []
            self.args = args
            self.queue = queue
            self.errorreport = False
            self.timeout = timeout
            self.result = None
            self.parent = None
            self.resultcode = None
            self.state = "SCHEDULED"  # SCHEDULED,STARTED,ERROR,OK,NOWORK
            self.timeStop = 0
            self.timeStart = 0
            self.timeCreate = j.data.time.getTimeEpoch()
            self.log = log
            self.internal = internal

    def setArgs(self, action):
        import inspect
        args = inspect.getargspec(action)
        # args.args.remove("session")
        # methods[name] = {'args' : args, 'doc': inspect.getdoc(method)}
        self.args = args.args
        self.argsDefaults = args.defaults
        self.argsVarArgs = args.varargs
        self.argsKeywords = args.keywords
        source = inspect.getsource(action)
        splitted = source.split("\n")
        splitted[0] = splitted[0].replace(action.__name__, "action")
        self.source = "\n".join(splitted)

    def getSetGuid(self):
        """
        use osis to define & set unique guid (sometimes also id)
        """
        self.gid = int(self.gid)
        self.id = int(self.id)
        # need to make sure roles & source cannot be changed
        self.guid = j.data.hash.sha256_string(self.getContentKey())

        return self.guid

    def getContentKey(self):
        """
        is like returning the hash, is used to see if object changed
        """
        # out=""
        # for item in ["cmd","category","args","source"]:
        #     out+=str(self.__dict__[item])
        return j.data.hash.md5_string(str(self.__dict__))

    def load(self, ddict):
        self.__dict__ = ddict


class RedisWorkerFactory(object):
    """
    """

    def __init__(self):
        self.log = j.logger.get('redisworkerfactory')
        self.__jslocation__ = "j.legacy.redisworker"

        random = j.data.idgenerator.generateGUID()
        self.sessionid = "%s_%s_%s_%s" % (
            j.application.whoAmI.gid, j.application.whoAmI.nid, j.application.whoAmI.pid, random)
        self.returnQueues = {}
        self._redis = None
        self._queue = None

    @property
    def redis(self):
        return j.core.db

    @property
    def queue(self):
        if self._queue is None:
            self._queue = {}
            self._queue["io"] = self.redis.getQueue("system")
            self._queue["hypervisor"] = self.redis.getQueue("workers:work:hypervisor")  # , fromcache=False)
            self._queue["default"] = self.redis.getQueue("workers:work:default")  # , fromcache=False)
            self._queue["process"] = self.redis.getQueue("workers:work:process")  # , fromcache=False)
        return self._queue

    def _getJob(self, jscriptid=None, args={}, timeout=60, log=True, queue="default", ddict={}, internal=True):
        job = Job(ddict=ddict, args=args, timeout=timeout, sessionid=self.sessionid, jscriptid=jscriptid, log=log,
                  queue=queue, internal=internal)
        job.id = self.redis.incr("workers:joblastid")
        job.getSetGuid()
        return job

    def getJob(self, jobid):
        jobdict = self.redis.get("workers:jobs:%s" % jobid)
        if jobdict:
            jobdict = json.loads(jobdict)
        else:
            raise KeyError("cannot find job with id:%s" % jobid)
        return jobdict

    def getJumpscriptFromId(self, jscriptid):
        jsdict = self.redis.hget("workers:jumpscripts:id", jscriptid)
        if jsdict:
            jsdict = json.loads(jsdict)
        else:
            return None

        return Jumpscript(ddict=jsdict)

    def deleteJumpscripts(self):
        for item in ["workers:jumpscripts:id", "workers:jumpscripts:name"]:
            self.redis.delete(item)

    def deleteQueues(self):
        for item in ["queues:workers:work:process", "queues:workers:work:io", "queues:workers:work:hypervisor",
                     "queues:workers:work:default"]:
            self.redis.delete(item)

    def deleteProcessQueue(self):
        for item in ["queues:workers:work:process", "workers:inqueuetest"]:
            self.redis.delete(item)

    def getJumpscriptFromName(self, organization, name):
        key = "%s__%s" % (organization, name)
        jsdict = self.redis.hget("workers:jumpscripts:name", key)
        if jsdict:
            jsdict = json.loads(jsdict)
        else:
            return None
        return Jumpscript(ddict=jsdict)

    def execFunction(self, method, _category="unknown", _organization="unknown", _timeout=60, _queue="default",
                     _log=True, _sync=True, **args):
        """
        @return job
        """
        source = inspect.getsource(method)
        sourcetmpl = """
from JumpScale import j
def action%(argspec)s:
%(source)s
    return %(funcname)s(%(args)s)
"""
        while True:
            try:
                source = j.code.deIndent(source)
            except:
                break  # reached maximum dedent
        spec = inspect.getargspec(method)
        argspec = inspect.formatargspec(spec.args, spec.varargs, spec.keywords, spec.defaults)
        source = sourcetmpl % {'argspec': argspec,
                               'funcname': method.__name__,
                               'source': j.code.indent(source),
                               'args': ', '.join(spec.args)}

        js = Jumpscript()
        js.source = source
        js.organization = _organization
        js.name = method.__name__
        key = j.data.hash.md5_string(source)

        if self.redis.hexists("workers:jumpscripthashes", key):
            js.id = self.redis.hget("workers:jumpscripthashes", key)
            # js=Jumpscript(ddict=json.loads(jumpscript_data))
        else:
            # jumpscript does not exist yet
            js.id = self.redis.incr("workers:jumpscriptlastid")
            jumpscript_data = json.dumps(js.__dict__)
            self.redis.hset("workers:jumpscripts:id", js.id, jumpscript_data)
            if js.organization != "" and js.name != "":
                self.redis.hset("workers:jumpscripts:name", "%s__%s" % (js.organization, js.name), jumpscript_data)
            self.redis.hset("workers:jumpscripthashes", key, js.id)

        job = self._getJob(js.id, args=args, timeout=_timeout, log=_log, queue=_queue, internal=True)
        job.cmd = js.name
        self._scheduleJob(job)
        if _sync:
            job = self.waitJob(job, timeout=_timeout)
            return job.result
        else:
            return job

    def checkJumpscriptQueue(self, jumpscript, queue):
        """
        this checks that jumpscripts are not executed twice when being scheduled recurring
        one off jobs will always execute !!!
        """
        if jumpscript.period > 0:
            # check of already in queue
            if self.redis.hexists("workers:inqueuetest", jumpscript.getKey()):
                inserttime = self.redis.hget("workers:inqueuetest", jumpscript.getKey())
                if inserttime is not None and int(inserttime) < (
                        int(time.time()) - 3600):  # when older than 1h remove no matter what
                    self.redis.hdel("workers:inqueuetest", jumpscript.getKey())
                    self.checkQueue()
                    return False
                print(("%s is already scheduled" % jumpscript.name))
                return True
        return False

    def execJumpscript(self, jumpscriptid=None, jumpscript=None, _timeout=60, _queue="default", _log=True, _sync=True,
                       **args):
        """
        @return job
        """
        js = jumpscript
        if js is None:
            js = self.getJumpscriptFromId(jumpscriptid)
            if js is None:
                raise RuntimeError("Cannot find jumpscript with id:'%s' on worker." % jumpscriptid)
        else:
            js = jumpscript

        if self.checkJumpscriptQueue(js, _queue):
            return None
        job = self._getJob(js.id, args=args, timeout=_timeout, log=_log, queue=_queue, internal=True)
        job.cmd = js.name
        job.category = js.organization
        job.log = js.log
        self.redis.hset("workers:inqueuetest", js.getKey(), int(time.time()))
        self._scheduleJob(job)
        if _sync:
            job = self.waitJob(job, timeout=_timeout)
        return job

    def execJobAsync(self, job):
        print(("execJobAsync:%s" % job["id"]))
        job = Job(ddict=job)
        self._scheduleJob(job)
        return job

    def checkQueue(self):
        return
        db = self.redis
        for name in ["process", "hypervisor", "default", "io"]:
            qname = "queues:workers:work:%s" % name
            for i in range(db.llen(qname)):
                jobbin = db.lindex(qname, i)
                print(jobbin)
                # @todo needs to be implement, need to check there are no double recurring jobs, need to check jumpscripts exist, need to check jobs are also in redis, ...

    def _getWork(self, qname, timeout=0):
        if qname not in self.queue:
            raise RuntimeError("Could not find queue to execute job:%s ((ops:workers.schedulework L:1))" % qname)

        queue = self.queue[qname]
        actionqueue = "workers:action:%s" % qname

        if timeout != 0:
            result = self.redis.blpop([queue.key, actionqueue], timeout=timeout)
        else:
            result = self.redis.blpop([queue.key, actionqueue])
        if result is None:
            return None, None

        if result[0] == actionqueue:
            return "action", result[1]
        else:
            jobdict = result[1]
            jobdict = json.loads(jobdict)
            return "job", Job(ddict=jobdict)

    def waitJob(self, job, timeout=600):
        result = self.redis.blpop("workers:return:%s" % job.id, timeout=timeout)
        if result is None:
            job.state = "TIMEOUT"
            job.timeStop = int(time.time())
            self.redis.set("workers:jobs%s" % job.id, json.dumps(job.__dict__), ex=60)
            j.events.opserror("timeout on job:%s" % job, category='workers.job.wait.timeout', e=None)
        else:
            job = self.getJob(job.id)

        job = Job(ddict=job)
        if job.state != "OK":
            eco = j.errorconditionhandler.getErrorConditionObject(ddict=job.result)
            # eco.process()
            raise RuntimeError("Could not execute job, error:\n%s" % str(eco))  # @todo is printing too much
        return job

    def _scheduleJob(self, job):
        """
        """

        qname = job.queue
        if not qname or qname.strip() == "":
            qname = "default"

        if qname not in self.queue:
            raise RuntimeError("Could not find queue to execute job:%s ((ops:workers.schedulework L:1))" % job)

        queue = self.queue[qname]

        # if not self.jobExistsInQueue(qname,job):
        data = json.dumps(job.__dict__)
        self.redis.set("workers:jobs:%s" % job.id, data)
        queue.put(data)

    def scheduleJob(self, job):
        jobobj = Job(ddict=job)
        self._scheduleJob(jobobj)

    def getJobLine(self, job=None, jobid=None):
        if jobid is not None:
            job = self.getJob(jobid)
        start = j.data.time.epoch2HRDateTime(job['timeStart'])
        if job['timeStop'] == 0:
            stop = "N/A"
        else:
            stop = j.data.time.epoch2HRDateTime(job['timeStop'])
        jobid = '[%s|/grid/job?id=%s]' % (job['id'], job['id'])
        line = "|%s|%s|%s|%s|%s|%s|%s|%s|" % (
            jobid, job['state'], job['queue'], job['category'], job['cmd'], job['jscriptid'], start, stop)
        return line

    def getQueuedJobs(self, queue=None, asWikiTable=True):
        result = list()
        queues = [queue] if queue else ["io", "hypervisor", "default", 'process']
        for quename in queues:
            queue = self.queue[quename]
            jobs = self.redis.lrange(queue.key, 0, -1)
            for jobstring in jobs:
                result.append(json.loads(jobstring))
        if asWikiTable:
            out = ""
            for job in result:
                out += "%s\n" % self.getJobLine(job=job)
            return out
        return result

    def getFailedJobs(self, queue=None, hoursago=0):
        jobs = list()
        queues = (queue,) if queue else ('io', 'hypervisor', 'default')
        for q in queues:
            jobsjson = self.redis.lrange('queues:workers:work:%s' % q, 0, -1)
            for jobstring in jobsjson:
                jobs.append(json.loads(jobstring))

        # get failed jobs
        for job in jobs:
            if job['state'] not in ('ERROR', 'TIMEOUT'):
                jobs.remove(job)

        if hoursago:
            epochago = j.data.time.getEpochAgo(str(hoursago))
            for job in jobs:
                if job['timeStart'] <= epochago:
                    jobs.remove(job)
        return jobs

    def removeJobs(self, hoursago=48, failed=False):
        epochago = j.data.time.getEpochAgo(hoursago)
        for q in ('io', 'hypervisor', 'default'):
            jobs = dict()
            jobsjson = self.redis.hgetall('queues:workers:work:%s' % q)
            if jobsjson:
                jobs.update(json.loads(jobsjson))
                for k, job in list(jobs.items()):
                    if job['timeStart'] >= epochago:
                        jobs.pop(k)

                if not failed:
                    for k, job in list(jobs.items()):
                        if job['state'] in ('ERROR', 'TIMEOUT'):
                            jobs.pop(k)

                if jobs:
                    self.redis.hdel('queues:workers:work:%s' % q, list(jobs.keys()))

    def deleteJob(self, jobid):
        job = self.getJob(jobid)
        self.redis.hdel('queues:workers:work:%s' % job.queue, jobid)
