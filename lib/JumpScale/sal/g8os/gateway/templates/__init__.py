import jinja2
import os


def get(templatename):
    templatepath = os.path.dirname(__file__)
    loader = jinja2.FileSystemLoader(templatepath)
    env = jinja2.Environment(loader=loader)
    return env.get_template(templatename)


def render(templatename, **kwargs):
    env = get(templatename)
    return env.render(**kwargs) + '\n'
