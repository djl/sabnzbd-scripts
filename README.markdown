sabnzbd-scripts
---------------

Some custom SABnzbd post-processing scripts.


### guessit-renamer.py

Moves and renames files. Requires [Jinja2][j2] and [guessit][guessit].

### dirmerge.py

Merges two directories. Preserves duplicates by appending an
incremental number (e.g. `MyFile.txt, MyFile.1.txt, etc.`)

[j2]: http://jinja.pocoo.org/docs/dev/
[guessit]: https://pypi.python.org/pypi/guessit
