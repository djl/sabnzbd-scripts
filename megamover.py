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
from jinja2 import Template


CONFIG_FILE = '/etc/megamover.conf'
MOVIE_EXTENSIONS = ['mkv', 'avi', 'm4v', 'mp4']
SUB_EXTENSIONS = ['idx', 'sub', 'srt']
EXTENSIONS = MOVIE_EXTENSIONS + SUB_EXTENSIONS


def echo(msg=''):
    sys.stdout.write(msg + '\n')
    sys.stdout.flush()


def fail(msg):
    sys.stderr.write(msg + '\n')
    sys.stderr.flush()
    sys.exit(1)


def fmt(tmpl, context):
    try:
        tmpl = open(tmpl).read()
    except IOError:
        fail('Could not read config file')

    tmpl = Template(tmpl).render(**context)
    configstr = StringIO(tmpl)
    config = configparser.ConfigParser()
    config.readfp(configstr)
    return config


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
    if not os.path.isfile(fn):
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

    for fn in files:
        # Sometimes the file name is encoded garbage but the job name
        # is always correct. Use $JOB_NAME.$FILE_EXT as the file name
        # instead so we get the correct data
        fn_job = "%s.%s" % (job_name, os.path.splitext(fn)[-1])
        info = guess_file_info(os.path.basename(fn_job))

        config = fmt(CONFIG_FILE, info)

        try:
            category_types = config.get('types', category).split()
        except configparser.nosectionerror, configparser.NoOptionError:
            category_types = []

        if category_types and category not in category_types:
            fail("Media type '%s' does not match expected category '%s'" % (info['type'], category))

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
