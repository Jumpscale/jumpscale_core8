from collections import OrderedDict

import msgpack
from JumpScale import j
from JumpScale.baselib.atyourservice81.lib.models.ActorServiceBaseModel import ActorServiceBaseModel
from JumpScale.baselib.atyourservice81.lib.Actor import Actor


class ActorModel(ActorServiceBaseModel):
    """
    Model Class for an Actor object
    """

    def index(self):
        # put indexes in db as specified
        ind = "%s:%s" % (self.dbobj.name, self.dbobj.state)
        self._index.index({ind: self.key})

    @property
    def role(self):
        return self.dbobj.name.split(".")[0]

    def objectGet(self, aysrepo):
        """
        returns an Actor object created from this model
        """
        actor = Actor(aysrepo=aysrepo, model=self)
        return actor

    def updateEventDict(self, ddict):
        ddict = j.data.capnp.tools.listInDictCreation(ddict, "events")
        ddict = j.data.capnp.tools.listInDictCreation(ddict, "secrets")
        return ddict

    def parentSet(self, role, auto=True, optional=False, argname=""):
        changed = False
        if role != self.dbobj.parent.actorRole:
            self.dbobj.parent.actorRole = role
            changed = True

        self.dbobj.parent.minServices = 1
        self.dbobj.parent.maxServices = 1

        if auto != self.dbobj.parent.auto:
            self.dbobj.parent.auto = auto
            changed = True

        if optional != self.dbobj.parent.optional:
            self.dbobj.parent.optional = optional
            changed = True

        if argname != self.dbobj.parent.argname:
            self.dbobj.parent.argname = argname
            changed = True

        self.changed = changed

        return changed

# producers
    def producerAdd(self, role, min=1, max=1, auto=True, optional=False, argname=""):
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
        o = j.data.capnp.getMemoryObj(
                self._capnp_schema.ActorPointer,
                actorRole=role, minServices=int(min), maxServices=int(max),
                auto=bool(auto), optional=bool(optional), argname=argname
            )
        self.dbobj.producers.append(o)

    @property
    def dictFiltered(self):
        ddict = self.dbobj.to_dict()
        if "data" in ddict:
            ddict.pop("data")
        return ddict

    def _pre_save(self):
        pass

    def actionSet(self, name, key="", period=0, log=True, state="new"):
        """
        creates and add an action code model to the actor/service

      struct Action {
        name @0 :Text;
        #unique key for code of action (see below)
        actionKey @1 :Text;
        period @2 :UInt32; #use j.data.time.getSecondsInHR( to show HR
        log @3 :Bool;
        state @4 :ActionState;
      }

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
                name=name, actionKey=key, period=period, log=log, state=state
            )
            self.dbobj.actions.append(action_obj)
            # action_obj = self.addSubItem("producers", msg)

        if key == "":
            raise j.exceptions.Input(message="action key cannot be empty", level=1, source="", tags="", msgpub="")

        action_obj.actionKey = key

        if action_obj.period != period:
            action_obj.period = period
            self.changed = True
        if action_obj.log != log:
            action_obj.log = log
            self.changed = True

        return action_obj
