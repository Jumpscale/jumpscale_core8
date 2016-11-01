# AtYourService v8.1

## What's new ?
- Usage of a key value store to persists data instead of plain files.
- Multiprocessing that allow parallel execution of the actions.
- Usage of [Cap’n Proto](https://capnproto.org/capnp-tool.html) to model the schema of the services.
- New format for the actions files.
- Daemon mode

### Key value store :
The introduction of the key value store allow AYS to scale better. In the previous version, when loading,
AYS had to walk over a big number of files and redo a lot of work to actually load the service in memory.
Now with the key value store, loading a service is as simple a doing a query to the store.

The current key value store use is [Redis](http://redis.io/). This has been choosen for ease of development and because JumpScale already use redis internally.
 But eventually we could replace redis with any key value store. It could be a distributed key value store to make AYS work in the cloud or a more performance oriented store if it's needed.

### Multiprocessing :
In this version of AYS we still have the concept of Run. A run is an atomic piece of work that result in the execution of an action on a full AYS repository.
A run is composed of steps. A step is basically the different actions the services need to execute in a run. All actions in a step can be execute in parallel.
In this version of AYS we use multiprocessing to process this task in parallel. This gives a great speed boost when you deploy a big blueprint that have lots of component that don't hardly depend on each others.

### Cap'n Proto
This format has been chosen for its strict schema definition and its rapidity to serialize data.
Currently the actor templates still use HRD to define the schema and then the HRD is internally converted into capnp. But eventually we'll migrate to capnpn only schema.

### Action files format :
In the previous version of AYS we used to write the actions file as a python class. Each method of the class was an action.
It was like that for historical reason and implementation detail.
In this new version we simplify the action file to be a python file where we simply define methods.
This brings two things, first it force the person that write the action code to thing about the action in an atomic piece of work.
Since now the actions can be executed in parallel they can't share state, so having them in separated method instead of in a class help to write clean and self-contained code.
Secondly in the future we could distribute the execution of these action over multiple servers. So once again having self-contains function makes it easier to distribute.
