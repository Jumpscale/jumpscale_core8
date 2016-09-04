@0x93c1ac9f09464fd6;

struct Actor {

  state @0 :State;
  enum State {
    new @0;
    ok @1;
    error @2;
    disabled @3;
  }

  #name of actor e.g. node.ssh (role is the first part of it)
  name @1 :Text;

  #dns name of actor who owns this service
  actorFQDN @2 :Text;

  parent @3 :ActorPointer;

  producers @4 :List(ActorPointer);

  struct ActorPointer {
    name @0 :Text;
    actorFQDN @1 :Text;
    maxServices @2 :UInt8;
    actorKey @3 :Text;
  }

  actions @5 :List(Action);
  struct Action {
    name @0 :Text;
    #unique key for code of action (see below)
    actionCodeKey @1 :Text;
    type @2 :Type;
    enum Type {
      actor @0;
      service @1;
      node @2;
    }
  }

  recurringTemplate @6 :List(Recurring);
  struct Recurring {
    #period in seconds
    action @0 :Text;
    period @1 :UInt32;
    #if True then will keep log of what happened, otherwise only when error
    log @2 :Bool;
  }

  #capnp
  serviceDataSchema @7 :Text;
  actorDataSchema @8 :Text;

  origin @9 :Origin;
  struct Origin {
    #link to git which hosts this template for the actor
    gitUrl @0 :Text;
    #path in that repo
    path @1 :Text;
  }

  #python script which interactively asks for the information when not filled in
  serviceDataUI @10 :Text;
  actorDataUI @11 :Text;

  serviceDataSchemaHRD @12 :Text;
  actorDataSchemaHRD @13 :Text;


}

struct Service {
  #is the unique deployed name of the service of a specific actor name e.g. myhost
  name @0 :Text;

  #name of actor e.g. node.ssh
  actorName @1 :Text;

  #FQDN of actor who owns this service
  actorFQDN @2 :Text;

  parent @3 :ServicePointer;

  producers @4 :List(ServicePointer);

  struct ServicePointer {
    name @0 :Text;
    actorName @1 :Text;
    #domain name of actor who owns this service pointed too
    actorFQDN @2 :Text;
    #defines which rights this service has to the other service e.g. owner or not
    key @3 :Text;

  }

  actions @5 :List(Action);

  struct Action {
    #e.g. install
    name @0 :Text;
    #unique key for code of action (see below)
    actionCodeKey @1 :Text;
    state @2: State;
  }

  recurring @6 :List(Recurring);
  struct Recurring {
    #period in seconds
    action @0 :Text;
    period @1 :UInt32;
    lastRun @2: UInt32;
    # needs to be bool
    # if True then will keep log of what happened, otherwise only when error
    log @3: Bool;
  }

  state @7 :State;
  enum State {
    new @0;
    installing @1;
    ok @2;
    error @3;
    disabled @4;
    changed @5;
  }

  configData @8 :Data;
  # bytes version of the content of schema.hrd after translation to canpn

  #schema of config data in textual format
  capnpSchema @9 :Text;

  gitRepos @10 :List(GitRepo);
  struct GitRepo {
    #git url
    url @0 :Text;
    #path in repo
    path @1 :Text;
  }

}

#is one specific piece of code which can be executed
#is owned by a ACTOR_TEMPLATE specified by actor_name e.g. node.ssh
#this is used to know which code was executed and what exactly the code was
struct ActionCode {

  #name of the method e.g. install
  name @0 :Text;

  #actor name e.g. node.ssh, is unique over all actors in world
  actorName @1 :Text;

  code @2 :Text;

  lastModDate @3: UInt32;

  args @4 :List(Argument);
  struct Argument {
    name @0: Text;
    defval @1: Data;
    }
}

struct Run {
    #this object is hosted by actor based on FQDN

    #which step is running right now, can only move to net one if previous one was completed
    currentStep @0: UInt16;

    #FQDN of a specific actor which can run multiple jobs & orchestrate work
    aysControllerFQDN @1 :Text;

    steps @2 :List(RunStep);
    struct RunStep {
      epoch @0: UInt32;
      state @1 :State;
      #list of jobs which need to be executed, key alone is enough to fetch the job info
      jobs @2 :List(Job);
      struct Job {
          guid @0 :Text;

          #NEXT IS CACHED INFO, THE MAIN SOURCE OF NEXT INFO IS IN Job
          #BUT is good practice will make all run very much faster& allow fast vizualization
          state @1 :State;
          #e.g. node.ssh
          actorName @2 :Text;
          #name e.g. install
          actionName @3 :Text;
          #name of service run by actor e.g. myhost
          serviceName @4 :Text;
      }
    }

    #state of run in general
    state @3 :State;
    enum State {
        new @0;
        running @1;
        ok @2;
        error @3;
    }

    lastModDate @4: UInt32;



}


struct Job {
  #this object is hosted by actor based on FQDN
  #is the run which asked for this job
  runGuid @0 :Text;

  #role of service e.g. node.ssh
  actorName @1 :Text;

  #name e.g. install
  actionName @2 :Text;

  #FQDN of actor who owns this service
  actorFQDN @3 :Text;

  #name of service run by actor e.g. myhost
  serviceName @4 :Text;

  #has link to code which needs to be executed
  actionCodeGUID @5 :Text;

  stateChanges @6 :List(StateChange);

  struct StateChange {
    epoch @0: UInt32;
    state @1 :State;
  }

  logs @7 :List(LogEntry);

  struct LogEntry {
    epoch @0: UInt32;
    log @1 :Text;
    level @2 :Int8; #levels as used in jumpscale
    category @3 :Cat;
    enum Cat {
      out @0; #std out from executing in console
      err @1; #std err from executing in console
      msg @2; #std log message
      alert @3; #alert e.g. result of error
      errormsg @4; #info from error
      trace @5; #e.g. stacktrace
    }
    tags @4 :Text;
  }

  #info which is input for the action, will be given to methods as service=...
  argsCapnp @8 :Data;
  #any other format e.g. binary or text or ... is up to actionmethod to deserialize & use, normally, will be given to method as data=...
  argsData @9 :Data;
  #dict which will be given to method as **args
  argsJson @10 :Data;


  #is the last current state
  state @11 :State;
  enum State {
      new @0;
      running @1;
      ok @2;
      error @3;
  }

  #json serialized result (dict), if any
  result @12 :Text;

}
