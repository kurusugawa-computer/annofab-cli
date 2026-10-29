import numpy
import pytest

from annofabcli.statistics.histogram import get_bin_edges


@pytest.mark.parametrize(
    ("min_value", "max_value", "bin_width", "expected"),
    [
        (0, 3, 2, [0, 2, 4]),
        (0, 4, 2, [0, 2, 4, 6]),
        (0, 0.2, 0.1, [0, 0.1, 0.2, 0.3]),
        (0, 0.3, 0.1, [0, 0.1, 0.2, 0.3, 0.4]),
        (0, 0.4, 0.1, [0, 0.1, 0.2, 0.3, 0.4, 0.5]),
        (0, 0.35, 0.1, [0, 0.1, 0.2, 0.3, 0.4]),
        (0.1, 0.3, 0.1, [0.1, 0.2, 0.3, 0.4]),
        (-0.3, 0, 0.1, [-0.3, -0.2, -0.1, 0, 0.1]),
        (0, 0, 0.1, [0, 0.1]),
    ],
)
def test_get_bin_edges(min_value, max_value, bin_width, expected):
    actual = get_bin_edges(min_value, max_value, bin_width)

    numpy.testing.assert_allclose(actual, expected, atol=1e-15)
    assert actual[-1] > max_value


def test_histogram_places_maximum_on_boundary_in_new_bin():
    bin_edges = get_bin_edges(min_value=0, max_value=4, bin_width=2)

    hist, _ = numpy.histogram([0, 1, 2, 3, 4], bins=bin_edges)

    numpy.testing.assert_array_equal(hist, [2, 2, 1])
