#!/usr/bin/env python
import os
import re
import sys
import unittest

np = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(np)

from guessitrenamer import renamer


class Tests(unittest.TestCase):
    def test_something(self):
        renamer('_meric.conf')


if __name__ == '__main__':
    unittest.main()
