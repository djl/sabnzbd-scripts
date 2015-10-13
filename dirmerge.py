#!/usr/bin/env python
"""
Usage: dirmerge.py <options> SRC DEST

Options:
  -n          perform a trial run with no changes made
  -d          delete any empty directories from SRC after merging
  -q          supress non-error messages
  -h          show this message and exit
"""
import errno
import optparse
import os
import shutil
import sys


def echo(msg='', dry_run=False):
    if dry_run:
        msg = '[DRY RUN] {0}'.format(msg)
    msg = '{0}\n'.format(msg).decode('utf-8', 'replace')
    sys.stdout.write(msg)
    sys.stdout.flush()


def usage():
    sys.stderr.write(__doc__.lstrip())
    sys.stdout.flush()
    sys.exit(1)


def find_empty_dirs(root_dir='.', recursive=True):
    empty_dirs = []
    for root, dirs, files in os.walk(root_dir, topdown=False):
        all_subs_empty = True
        for sub in dirs:
            full_sub = os.path.join(root, sub)
            if full_sub not in empty_dirs:
                all_subs_empty = False
                break
        if all_subs_empty and len(files) == 0:
            empty_dirs.append(root)
            yield root


def get_files(dirname):
    files = []
    for root, _, fns in os.walk(dirname):
        for fn in fns:
            abs = os.path.abspath(os.path.join(root, fn))
            files.append(abs)
    return files


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


def mkdirp(path):
    try:
        os.makedirs(path)
    except OSError as exc:
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise


def main():
    parser = optparse.OptionParser()
    parser.remove_option('--help')
    parser.add_option('-h', action='callback', callback=usage)
    parser.add_option('-n', action='store_true', dest='dry_run')
    parser.add_option('-d', action='store_true', dest='empty')
    parser.add_option('-q', action='store_true', dest='quiet')
    options, args = parser.parse_args()

    try:
        src, dest = args
    except ValueError:
        usage()

    src = os.path.abspath(src)
    dest = os.path.abspath(dest)

    # Just exit quietly if src or dest isn't a directory
    if not all([os.path.isdir(src), os.path.isdir(dest)]):
        return

    files = get_files(src)
    if not files:
        return

    for fn in files:
        prefix = os.path.commonprefix([src, fn])
        unprefixed = fn.split(prefix)[-1].lstrip('/')
        final = get_unique_filename(os.path.join(dest, unprefixed))
        if not options.dry_run:
            mkdirp(os.path.dirname(final))
            shutil.move(fn, final)
        if not options.quiet:
            echo("New file: %s (%s)" % (final, unprefixed), options.dry_run)

    if not options.empty:
        return

    empty = find_empty_dirs(src)
    if not empty and not options.quiet:
        echo("Skipped non-empty directory: %s" % src, options.dry_run)
        return

    for e in empty:
        if not options.dry_run:
            os.rmdir(e)
    if not options.quiet:
        echo("Removed empty directory: %s" % src, options.dry_run)


if __name__ == '__main__':
    main()
