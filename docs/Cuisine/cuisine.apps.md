# cuisine.apps

The `cuisine.apps` module is for application management.

Examples of methods inside an application:

- **build**: builds an application on the specified target, it takes arguments needed for building and an optional start kwarg for starting the application after building it
- **start**: starts an application
- **stop**: stops an application

## Applications that are currently supported

```
cockpit
controller (g8os controller)
core (g8os core)
deployerbot
etcd
fs (g8way FileSystem)
grafana
influxdb
mongodb
portal
redis
skydns
stor
syncthing
vulcand
weave
```
