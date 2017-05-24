# Click library has some problems with python3 when it comes to unicode: http://click.pocoo.org/5/python3/#python3-surrogates
# to fix this we need to set the environ variables to export the locales
import os
os.environ['LC_ALL'] = 'C.UTF-8'
os.environ['LANG'] = 'C.UTF-8'
import click
import logging
from JumpScale import j
from JumpScale.baselib.atyourservice81.server.app import app as sanic_app
sanic_app.config['REQUEST_TIMEOUT'] = 3600


def configure_logger(level):
    if level == 'DEBUG':
        click.echo("debug logging enabled")
    # configure jumpscale loggers
    j.logger.set_level(level)
    # configure asyncio logger
    for l in ('asyncio', 'g8core'):
        logger = logging.getLogger(l)
        logger.handlers = []
        logger.addHandler(j.logger.handlers.consoleHandler)
        logger.addHandler(j.logger.handlers.fileRotateHandler)
        logger.setLevel(level)


@click.command()
@click.option('--host', '-h', default='127.0.0.1', help='listening address')
@click.option('--port', '-p', default=5000, help='listening port')
@click.option('--log', '-l', default='info', help='set logging level (error, warning, info, debug)')
@click.option('--dev', default=False, is_flag=True, help='enable development mode')
def main(host, port, log, dev):
    log = log.upper()
    if log not in ('ERROR', 'WARNING', 'INFO', 'DEBUG'):
        click.echo("logging level not valid", err=True)
        return

    configure_logger(log)
    debug = log == 'DEBUG'

    # load the app
    @sanic_app.listener('before_server_start')
    async def init_ays(sanic, loop):
        loop.set_debug(debug)
        j.atyourservice.debug = debug
        j.atyourservice.dev_mode = dev
        if j.atyourservice.dev_mode:
            j.atyourservice.logger.info("development mode enabled")
        j.atyourservice._start(loop=loop)

    @sanic_app.listener('after_start')
    async def after_start(sanic, loop):
        print("AYS server running at http://{}:{}".format(host, port))

    @sanic_app.listener('after_stop')
    async def stop_ays(sanic, loop):
        await j.atyourservice._stop()
        loop.close()

    # start server
    sanic_app.run(debug=debug, host=host, port=port, workers=1)


if __name__ == '__main__':
    main()
