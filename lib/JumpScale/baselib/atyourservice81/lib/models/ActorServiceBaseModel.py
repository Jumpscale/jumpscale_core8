from collections import OrderedDict

import msgpack
from JumpScale import j

ModelBaseWithData = j.data.capnp.getModelBaseClassWithData()


class ActorServiceBaseModel(ModelBaseWithData):
    """
    Base class for ActorModel and ServiceModel class.
    You should not instanciate this class directly but one of its children instead
    """

    def __init__(self, aysrepo, capnp_schema, category, db, index, key="", new=False):
        super().__init__(capnp_schema=capnp_schema, category=category, db=db, index=index, key=key, new=new)
        self._aysrepo = aysrepo

    @property
    def name(self):
        if self.dbobj.name.strip() == "":
            raise j.exceptions.Input(message="name of actor or service cannot be empty in model",
                                     level=1, source="", tags="", msgpub="")
        return self.dbobj.name

    def recurringAdd(self, role, min=1, max=1, auto=True, optional=False, argname=""):
        """
          struct ActorPointer {
            actorRole @0 :Text;
            minServices @1 :UInt8;
            maxServices @2 :UInt8;
            auto @3 :Bool;
            optional @4 :Bool;
            argname @5 :Text; # key in the args that contains the instance name of the targets
          }
        """
        msg = self._capnp_schema.ActorPointer.new_message(actorRole=role, minServices=int(min), maxServices=int(max),
                                                          auto=bool(auto), optional=bool(optional), argname=argname)
        self.addSubItem("producers", msg)

    def actionAdd(self, name, key="", period=0, log=True):
        """
        creates and add an action code model to the actor/service
        """
        action_obj = None
        for act in self.dbobj.actions:
            if act.name == name:
                action_obj = act
                if key != "" and action_obj.actionKey != key:
                    action_obj.state = "changed"
                    self.changed = True
                break

        if j.data.types.string.check(period):
            period = j.data.time.getDeltaTime(period)

        if action_obj is None:
            action_obj = j.data.capnp.getMemoryObj(
                self._capnp_schema.Action,
                name=name, period=period, log=log, state='new', actionKey=key
            )
            self.changed = True
            if key == "":
                raise j.exceptions.Input(message="key cannot be empty when adding action:%s to %s" %
                                         (name, self), level=1, source="", tags="", msgpub="")
            self.dbobj.actions.append(action_obj)

        if key != "":
            action_obj.actionKey = key

        need2save = False
        if action_obj.period != period:
            action_obj.period = period
            self.changed = True
        if action_obj.log != log:
            action_obj.log = log
            self.changed = True

        return action_obj
# actions

    @property
    def actionsSortedList(self):
        """
        Sorted methods of the actor
        """
        if len(self.dbobj.actions) == 0:
            return []
        keys = sorted([item.name for item in self.dbobj.actions])
        return keys

    @property
    def actionsCode(self):
        """
        return dict
            key = action name
            val = source code of the action
        """
        methods = {}
        for action in self.dbobj.actions:
            action_model = j.core.jobcontroller.db.actions.get(action.actionKey)
            methods[action.name] = action_model.code
        return methods

    @property
    def actionsSourceCode(self):
        out = ""
        for action in self.dbobj.actions:
            actionKey = action.actionKey
            actionCode = j.core.jobcontroller.db.actions.get(actionKey)
            defstr = ""
            # defstr = "@%s\n" % action.type
            defstr += "def %s (%s):\n" % (actionCode.dbobj.name, actionCode.dbobj.args)
            if actionCode.dbobj.doc != "":
                defstr += "    '''\n    %s\n    '''\n" % actionCode.dbobj.doc

            if actionCode.dbobj.code == "":
                defstr += "    pass\n\n"
            else:
                if actionCode.dbobj.code != "":
                    defstr += "%s\n" % j.data.text.indent(actionCode.dbobj.code, 4)

            out += defstr
        return out

    @property
    def actions(self):
        """
        return dict of action pointer model
        key = action name
        value = action pointer model
        """
        actions = {}
        for act in self.dbobj.actions:
            actions[act.name] = act
        return actions

    @property
    def actionsRecurring(self):
        """
        return dict
            key = action name
            val = recurring model
        """
        recurrings = {}
        for obj in self.dbobj.actions:
            if obj.period != 0:
                recurrings[obj.name] = obj
        return recurrings

    @property
    def eventFilters(self):
        return list(self.dbobj.eventFilters)

    def actionDelete(self, name):
        for i, action in enumerate(self.dbobj.actions):
            if action.name == name:
                self.dbobj.actions.pop(i)
                self.changed = True
                return

    def actionGet(self, name, die=True):
        for action in self.dbobj.actions:
            if action.name == name:
                return action
        if die:
            raise j.exceptions.NotFound("Can't find method with name %s" % name)

    @property
    def actionsState(self):
        """
        return dict
            key = action name
            val = state
        state = 'new', 'installing', 'ok', 'error', 'disabled', 'changed'
        """
        actions = {}
        for action in self.dbobj.actions:
            actions[action.name] = action.state.__str__()
        return actions


# others

    def _pre_save(self):
        pass

    def __repr__(self):
        out = self.dictJson + "\n"
        if self.dbobj.data not in ["", b""]:
            out += "CONFIG:\n"
            out += self.dataJSON
        return out

    __str__ = __repr__
