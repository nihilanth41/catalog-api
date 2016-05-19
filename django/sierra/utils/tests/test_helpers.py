from __future__ import unicode_literals
import pytest

from .. import helpers as h


# For each type of call number, where the type is in the dict key, the
# first string in each tuple should sort before the second.
SORT_TEST_PARAMS = {
    'lc': [
        ('A', 'AA'),
        ('AA', 'AB'),
        ('AB', 'B'),
        ('A 1', 'A 2'),
        ('A 2', 'A 11'),
        ('A 1', 'A 1.1'),
        ('A 1.11', 'A 1.2'),
        ('A 1', 'A 1 .A1'),
        ('A 1 .A1', 'A 1 .B1'),
        ('A 1 .B1', 'A 1 .B2'),
        ('A 1 .B11', 'A 1 .B2'),
        ('A 1 .B1', 'A 1 .B1 C1'),
        ('A 1 .B1 C1', 'A 1 .B1 D1'),
        ('A 1 .B1 C1', 'A 1 .B1 C2'),
        ('A 1 .B1 C11', 'A 1 .B1 C2'),
        ('A 1 .B1 C1', 'A 1 .B1 C1 1999'),
        ('A 1 .B1 C1 1999', 'A 1 .B1 C1 2000'),
        ('A 1 .B1 C1 2000 no.1', 'A 1 .B1 C1 2000 no.2'),
    ],
    'sudoc': [
        ('A:', 'AA:'),
        ('AA:', 'AB:'),
        ('AB:', 'B:'),
        ('A 1:', 'A 2:'),
        ('A 2:', 'A 11:'),
        ('A 1:', 'A 1.1:'),
        ('A 1.1:', 'A 1.2:'),
        ('A 1.2:', 'A 1.11:'),
        ('A 1.1:', 'A 1.1/1:'),
        ('A 1.1/1:', 'A 1.1/2:'),
        ('A 1.1/2:', 'A 1.1/11:'),
        ('A 1.1/1:', 'A 1.1/1-1:'),
        ('A 1.1/1-1:', 'A 1.1/1-2:'),
        ('A 1.1/1-2:', 'A 1.1/1-11:'),
        ('A 1:', 'A 1:A'),
        ('A 1:A', 'A 1:B'),
        ('A 1:A', 'A 1:A 1'),
        ('A 1:A 1', 'A 1:A 2'),
        ('A 1:A 2', 'A 1:A 11'),
        ('A 1:A', 'A 1:1'),
        ('A 1:A', 'A 1:1'),
        ('A 1:1', 'A 1:2'),
        ('A 1:2', 'A 1:11'),
        ('A 1:799', 'A 1:899'),
        ('A 1:1999', 'A 1:2000'),
        ('A 1:1', 'A 1:1-1'),
        ('A 1:1-1', 'A 1:1-2'),
        ('A 1:1-2', 'A 1:1-11'),
        ('A 1:1', 'A 1:1/800'),
        ('A 1:1/800', 'A 1:1/2015'),
        ('A 1:1/2015', 'A 1:1/A'),
        ('A 1:1/A', 'A 1:1/B'),
        ('A 1:1/A', 'A 1:1/1'),
        ('A 1:1/1', 'A 1:1/2'),
        ('A 1:1/2', 'A 1:1/11'),
    ],
    'dewey': [
        ('100', '101'),
        ('100', '100.1'),
        ('100.1', '100.2'),
        ('100.11', '100.2'),
        ('100.1', '100.1 A'),
        ('100.1 A', '100.1 AA'),
        ('100.1 AA', '100.1 AB'),
        ('100.1 AB', '100.1 B'),
        ('100.1', 'A'),
        ('A', 'AA'),
        ('AA', 'AB'),
        ('AB', 'B'),
        ('AA', 'AA A'),
        ('AA A', 'AA AA'),
        ('AA AA', 'AA AB'),
        ('AA AB', 'AA B'),
    ],
    'other': [
        ('1', '2'),
        ('2', '11'),
        ('A', 'AA'),
        ('AA', 'AB'),
        ('AB', 'B'),
        ('A 1', 'A 2'),
        ('A 2', 'A 11'),
        ('A 1', 'A 2-3'),
        ('A 2-3', 'A 4')
    ],
    'default': [
        ('vol 1', 'vol 2'),
        ('1', '1.1'),
        ('1.1', '1.11'),
        ('1.11', '1.2'),
        ('1.2', '2'),
        ('2', '11'),
        ('A', 'AA'),
        ('AA', 'AB'),
        ('AB', 'B'),
    ]
}


# For each type of call number, where the type is in the dict key, the
# boolean in the tuple indicates if the two strings in the tuple should
# be equivalent--i.e., normalize to the same string.
EQUIVALENCY_TEST_PARAMS = {
    'lc': [
        ('A1', 'A 1', True),
        ('a 1', 'A 1', True),
        ('A 1.1', 'A 1.10', True),
        ('A 1.B2', 'A 1 .B2', True),
        ('A 1 .B2', 'A 1 .B 2', False),
        ('A 1 .b2', 'A 1 .B2', True),
        ('A 1 .B2 C3', 'A 1 .B2C3', True),
        ('A 1 .B2 c3', 'A 1 .B2 C3', True),
    ],
    'sudoc': [
        ('A 1:', 'A1:', True),
        ('a1:', 'A1:', True),
        ('A 1: A', 'A1:A', False),
        ('A 1:A 1', 'A1:A1', True),
    ],
    'dewey': [
        ('100.1', '100 .1', False),
        ('100 A', '100A', True),
        ('100 a', '100 A', True),
        ('AA', 'A A', False),
    ],
    'other': [
        ('A 1', 'A1', True),
        ('A 100,000', 'A 100000', True),
        ('a 1', 'A 1', True),
    ],
    'default': [
        ('1', 'v 1', True),
        ('1', 'V. 1', True),
        ('1', 'v1', True),
        ('1', 'v.1', True),
        ('1', 'vol 1', True),
        ('1', 'c 1', True),
        ('1', 'no 1', True),
    ],
    'search': [
        ('a', 'A', True),
        ('A1', 'A 1', True),
        ('A1', 'A.1', True),
        ('A1', 'A/1', True),
        ('A1', 'A,1', True),
        ('A1', 'A?1', True),
        ('A1', 'A-1', True),
        ('A1', 'A:1', False),
    ]
}


def flatten(params_dict):
    """
    Flattens a dict containing test parameters (such as
    SORT_TEST_PARAMS) into a list of tuples, where the dict key becomes
    one of the values in the list of tuples, to pass into a test
    function parametrized with @pytest.mark.parametrize.
    """
    flattened = []
    for kind, params in params_dict.iteritems():
        flattened.extend([(kind,) + p_tuple for p_tuple in params])
    return flattened


@pytest.mark.parametrize('kind,a,b', flatten(SORT_TEST_PARAMS))
def test_normalized_call_number_sorting(kind, a, b):
    norm = [h.NormalizedCallNumber(cn, kind=kind).normalize() for cn in (a, b)]
    assert norm[0] < norm[1]


@pytest.mark.parametrize('kind,a,b,expected', flatten(EQUIVALENCY_TEST_PARAMS))
def test_normalized_call_number_equivalency(kind, a, b, expected):
    norm = [h.NormalizedCallNumber(cn, kind=kind).normalize() for cn in (a, b)]
    assert (norm[0] == norm[1]) == expected
