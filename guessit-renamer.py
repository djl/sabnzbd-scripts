#!/usr/bin/env python
import errno
import os
import re
import shutil
import sys

try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

try:
    import configparser
except ImportError:
    import ConfigParser as configparser

from guessit import guess_file_info
from jinja2 import Environment
from jinja2.exceptions import UndefinedError


# TODO allow setting config file via env var
# TODO switch to something better than ini files. YAML/TOML?
CONFIG_FILE = '/etc/guessit-renamer.conf'
# TODO allow setting extensions via config file
MOVIE_EXTENSIONS = ['mkv', 'avi', 'm4v', 'mp4']
SUB_EXTENSIONS = ['idx', 'sub', 'srt']
EXTENSIONS = MOVIE_EXTENSIONS + SUB_EXTENSIONS

ENV = Environment(extensions=["jinja2.ext.do",])


# custom jinja2 filters
def pytitle(s):
    """
    Uses the titlecase module if available. Otherwise falls back to
    string's title() method.

    The built-in "title" filter clobbers acronyms.

    Jinja2:
    >>> {{ "hello A.B.C"|title }}
    'Hello A.b.c'

    Python:
    >>> 'Hello A.B.C'.title()
    'Hello A.B.C'

    Titlecase:
    >>> from titlecase import titlecase
    titlecase('Hello A.B.C')
    """
    try:
        import titlecase
        return titlecase.titlecase(s)
    except ImportError:
        return s.title()
    except UndefinedError:
        return s

ENV.filters['pytitle'] = pytitle


def resub(s, p, r):
    if not s:
        s = ''
    return re.sub(p, r, s)

ENV.filters['resub'] = resub


def echo(msg=''):
    msg = '{0}\n'.format(msg).decode('utf-8', 'replace')
    sys.stdout.write(msg)
    sys.stdout.flush()


def fail(msg):
    msg = '{0}\n'.format(msg).decode('utf-8', 'replace')
    sys.stderr.write(msg)
    sys.stderr.flush()
    sys.exit(1)


# TODO read the file once and re-use it so we don't parse
# it from disk each time
def fmt(tmpl, context):
    try:
        tmpl = open(tmpl).read()
    except IOError:
        fail('Could not read config file')

    tmpl = ENV.from_string(tmpl).render(**context)
    configstr = StringIO(tmpl)
    config = configparser.ConfigParser()
    config.readfp(configstr)
    return config


def check_required_fields(info, fields):
    for field in fields:
        if field not in info:
            return False
        return True


def get_suitable_files(dirname):
    # Get the largest files for each extension
    files = {}
    for root, _, fns in os.walk(dirname):
        for fn in fns:
            abs = os.path.abspath(os.path.join(root, fn))
            size = os.path.getsize(abs)
            ext = fn.rsplit('.', 1)[-1].lower()

            if ext not in EXTENSIONS:
                continue

            if ext not in files.keys():
                files[ext] = []

            files[ext].append((abs, size))

    # On the off-chance that we have multiple movie extensions, pick
    # the one we want
    # TODO: what if one of the lesser wanted files is the largest?
    for ext in MOVIE_EXTENSIONS:
        if ext in files.keys():
            unwanted = [e for e in MOVIE_EXTENSIONS if e != ext]
            for ext in unwanted:
                try:
                    del files[ext]
                except KeyError:
                    pass

    results = []
    for ext, items in files.items():
        item = sorted(items, key=lambda tup: tup[1], reverse=True)[0][0]
        results.append(item)

    return results


def get_unique_filename(fn):
    if not os.path.exists(fn):
        return fn

    name, ext = os.path.splitext(fn)
    count = 1
    while True:
        new_fn = "%s.%d%s" % (name, count, ext)
        if not os.path.exists(new_fn):
            return new_fn
        count += 1


def mkdirp(path, mode=0755):
    if not path.endswith(os.path.sep):
        path = path + os.path.sep

    paths = []
    while path:
        path = path.rsplit(os.path.sep, 1)[0]
        if not path:
            continue
        if not os.path.exists(path):
            paths.append(path)

    paths.reverse()

    for path in paths:
        os.mkdir(path, mode)
        os.chmod(path, mode)


def main(job_dir, job_name, category):
    files = get_suitable_files(job_dir)
    if not files:
        fail("No suitable files found")

    # Sometimes either the job name or the file names are encoded
    # garbage. First, check if the job name contains the info we need.
    # If it doesn't, loop over each file and check those instead.
    config = fmt(CONFIG_FILE, {})
    fn_job = "{0}.mkv".format(job_name)

    try:
        category_type = config.get('types', category)
    except configparser.NoSectionError, configparser.NoOptionError:
        category_type = None

    try:
        guessit_config = dict(config.items('guessit'))
    except configparser.NoSectionError:
        guessit_config = {}

    try:
        fields = config.get('required_fields', category)
        fields = fields.split(',')
    except configparser.NoSectionError, configparser.NoOptionError:
        fields = []

    info = guess_file_info(os.path.basename(fn_job),
                           type=category_type,
                           **guessit_config)

    if not check_required_fields(info, fields):
        info = None
        for fn in files:
            fn_info = guess_file_info(os.path.basename(fn),
                                      type=category_type,
                                      **guessit_config)
            if check_required_fields(fn_info, fields):
                info = fn_info
                break

        if not info:
            fail("Could not determine metadata for job: {0}".format(job_name))

    # Begin moving everything into place
    for fn in files:
        # Parse the config a second time with the full metadata for each
        # file
        info['extension'] = os.path.splitext(fn)[-1].strip('.')
        config = fmt(CONFIG_FILE, info)

        try:
            dest = config.get('categories', category)
        except configparser.NoSectionError, configparser.NoOptionError:
            fail("No config for category: %s" % category)

        dest = os.path.join(dest, get_unique_filename(dest))
        mkdirp(os.path.dirname(dest))
        shutil.move(fn, dest)
        echo("New file: %s (%s)" % (dest, os.path.basename(fn)))

    # Remove the job directory
    shutil.rmtree(job_dir)

    # try to remove the empty category directories
    parent_dirname = os.path.dirname(job_dir)
    parent_basename = os.path.basename(parent_dirname)
    if parent_basename.lower() == category.lower():
        try:
            os.rmdir(parent_dirname)
            echo("Removed empty directory: %s" % parent_dirname)
        except OSError:
            echo("Skipped non-empty directory: %s" % parent_dirname)
            pass


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[3], sys.argv[5])
