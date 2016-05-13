from __future__ import unicode_literals
import pytest

from .. import helpers as h


LC_NORMALIZATION_TEST_PARAMS = [
    ('AA', 'AA'),
    ('AA1111', 'AA!0000001111'),
    ('AA 1111', 'AA!0000001111'),
    ('AA1111A1111', 'AA!0000001111!A1111'),
    ('AA1111.A1111', 'AA!0000001111!A1111'),
    #('AA1111 .A1111', 'AA!0000001111!A1111'),
    ('AA1111. A1111', 'AA!0000001111!A1111'),
    ('AA1111.11.A1111 A1111 2000', 'AA!0000001111.11!A1111!A1111!0000002000'),
]

SUDOC_NORMALIZATION_TEST_PARAMS = [
    ('A 1111.1111:', 'A!0000001111!0000001111!0000000000!0000000000!'),
    ('A 1111.1111:1111', 'A!0000001111!0000001111!0000000000!0000000000!0000001111')
]


@pytest.mark.parametrize('cn, expected', LC_NORMALIZATION_TEST_PARAMS)
def test_lc_cn_normalization(cn, expected):
    assert h.NormalizedCallNumber(cn, 'lc').normalize() == expected


@pytest.mark.parametrize('cn, expected', SUDOC_NORMALIZATION_TEST_PARAMS)
def test_lc_cn_normalization(cn, expected):
    assert h.NormalizedCallNumber(cn, 'sudoc').normalize() == expected
