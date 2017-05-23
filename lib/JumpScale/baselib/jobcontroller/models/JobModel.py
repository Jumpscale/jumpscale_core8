from JumpScale import j

ModelBase = j.data.capnp.getModelBaseClass()

import importlib
import msgpack
from collections import OrderedDict

VALID_LOG_CATEGORY = ['out', 'err', 'msg', 'alert', 'errormsg', 'trace']


class JobModel(ModelBase):
    """
    """

    def index(self):
        # put indexes in db as specified
        res = self.collection._index.list("%s:%s:%s:.*:%s:.*" % (self.dbobj.actorName, self.dbobj.serviceName,
                                          self.dbobj.actionName, self.dbobj.serviceKey), returnIndex=True)
        for matched in res:
            self.collection._index.index_remove(matched[0])
        ind = "%s:%s:%s:%s:%s:%s" % (self.dbobj.actorName, self.dbobj.serviceName,
                                     self.dbobj.actionName, self.dbobj.state, self.dbobj.serviceKey, self.dbobj.lastModDate)
        self.collection._index.index({ind: self.key})

    def log(self, msg, level=5, category="msg", epoch=None, tags=''):
        """
        category:
              out @0; #std out from executing in console
              err @1; #std err from executing in console
              msg @2; #std log message
              alert @3; #alert e.g. result of error
              errormsg @4; #info from error
              trace @5; #e.g. stacktrace
        """
        if category not in VALID_LOG_CATEGORY:
            raise j.exceptions.Input('category %s is not a valid log category.' % category)

        if epoch is None:
            epoch = j.data.time.getTimeEpoch()

        logitem = self.collection.capnp_schema.LogEntry.new_message()
        logitem.category = category
        logitem.level = int(level)
        logitem.epoch = epoch
        logitem.log = msg.strip()
        logitem.tags = tags

        self.addSubItem('logs', logitem)
        self.reSerialize()

        return logitem

    @property
    def state(self):
        return self.dbobj.state.__str__()

    @state.setter
    def state(self, val):
        """
          enum State {
              new @0;
              running @1;
              ok @2;
              error @3;
              abort @4;
          }
        """
        sc = self._stateChangeObjNew()
        sc.epoch = j.data.time.getTimeEpoch()
        sc.state = val
        self.dbobj.lastModDate = sc.epoch
        self.dbobj.state = val

    def _stateChangeObjNew(self):
        olditems = [item.to_dict() for item in self.dbobj.stateChanges]
        newlist = self.dbobj.init("stateChanges", len(olditems) + 1)
        for i, item in enumerate(olditems):
            newlist[i] = item
        return newlist[-1]

    @property
    def args(self):
        if self.dbobj.args == b"":
            return {}
        res = msgpack.loads(self.dbobj.args, encoding='utf-8')
        # print("get:%s" % res)
        if res is None:
            res = {}
        return res

    @property
    def argsJons(self):
        ddict2 = OrderedDict(self.args)
        return j.data.serializer.json.dumps(ddict2, sort_keys=True, indent=True)

    @args.setter
    def args(self, val):
        args = msgpack.dumps(val)
        # print("set:%s" % args)
        self.dbobj.args = args

    @property
    def result(self):
        if self.dbobj.result == b"":
            return {}
        return msgpack.loads(self.dbobj.result, encoding='utf-8')

    @property
    def resultJons(self):
        ddict2 = OrderedDict(self.result)
        return j.data.serializer.json.dumps(ddict2, sort_keys=True, indent=True)

    @result.setter
    def result(self, val):
        result = msgpack.dumps(val)
        self.dbobj.result = result

    def objectGet(self):
        """
        returns an Job object created from this model
        """
        return j.core.jobcontroller.newJobFromModel(self)

    @property
    def dictFiltered(self):
        ddict = self.dbobj.to_dict()
        to_filter = ['args', 'result', 'profileData']
        for key in to_filter:
            if key in ddict:
                del ddict[key]
        return ddict

    def save(self):
        self._pre_save()
        if not self.collection._db.inMem:
            # expiration of 172800 = 2 days  expire=172800
            buff = self.dbobj.to_bytes()
            if hasattr(self.dbobj, 'clear_write_flag'):
                self.dbobj.clear_write_flag()
            self.collection._db.set(self.key, buff, expire=172800)
        self.index()

    def delete(self):
        # delete actual model object
        if self.collection._db.exists(self.key):
            index = "%s:%s:%s:%s:%s:%s" % (self.dbobj.actorName, self.dbobj.serviceName,
                                         self.dbobj.actionName, self.dbobj.state, self.dbobj.serviceKey, self.dbobj.lastModDate)
            self.collection._index.index_remove(keys=index)
            self.collection._db.delete(self.key)
            del self.logger

    def __repr__(self):
        out = self.dictJson + "\n"
        if self.dbobj.args not in ["", b""]:
            out += "args:\n"
            out += self.argsJons
        return out

    __str__ = __repr__
