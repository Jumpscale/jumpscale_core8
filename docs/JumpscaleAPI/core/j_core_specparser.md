<!-- toc -->
## j.core.specparser

- /opt/jumpscale8/lib/JumpScale/core/specparser/SpecParser.py
- Properties
    - specs
    - modelnames
    - roles
    - childspecs
    - app_actornames
    - appnames
    - actornames

### Methods

#### addSpec(*spec*) 

#### findSpec(*query='', appname='', actorname='', specname='', type='', findFromSpec, findOnlyOne=True*) 

```
do not specify query with one of the other filter criteria
@param query is in dot notation e.g. $appname.$actorname.$modelname ... the items in front
    are optional

```

#### getChildModelSpec(*app, actorname, name, die=True*) 

#### getEnumerationSpec(*app, actorname, name, die=True*) 

#### getModelNames(*appname, actorname*) 

#### getModelSpec(*app, actorname, name, die=True*) 

#### getSpecFromTypeStr(*appname, actorname, typestr*) 

```
@param typestr e.g list(machine.status)
@return $returntype,$spec  $returntype=list,dict,object,enum (list & dict can be of
    primitive types or objects (NOT enums))

```

#### getactorSpec(*app, name, raiseError=True*) 

#### init() 

#### parseSpecs(*specpath, appname, actorname*) 

```
@param specpath if empty will look for path specs in current dir

```

#### removeSpecsForactor(*appname, actorname*) 

#### resetMemNonSystem() 

