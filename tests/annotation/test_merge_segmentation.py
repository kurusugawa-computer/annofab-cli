import numpy
import pytest

from annofabcli.annotation.merge_segmentation import merge_binary_image_array


def test_merge_binary_image_array_basic():
    # 基本的な動作確認
    input_array1 = numpy.array([[False, True], [True, False]], dtype=bool)
    input_array2 = numpy.array([[True, False], [False, True]], dtype=bool)
    expected_output = numpy.array([[True, True], [True, True]], dtype=bool)
    actual_output = merge_binary_image_array([input_array1, input_array2])
    numpy.testing.assert_array_equal(actual_output, expected_output)


def test_merge_binary_image_array_error_handling():
    # エラーハンドリングの確認
    with pytest.raises(ValueError):
        merge_binary_image_array([])


def test_merge_binary_image_array_boundary():
    # 境界値テスト
    input_array1 = numpy.array([], dtype=bool)
    input_array2 = numpy.array([], dtype=bool)
    expected_output = numpy.array([], dtype=bool)
    actual_output = merge_binary_image_array([input_array1, input_array2])
    numpy.testing.assert_array_equal(actual_output, expected_output)
