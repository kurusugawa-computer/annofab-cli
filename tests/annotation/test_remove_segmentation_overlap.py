import numpy as np

from annofabcli.annotation.remove_segmentation_overlap import remove_overlap_of_binary_image_array


def test_remove_overlap_of_binary_image_array():
    # テスト用の入力データ
    binary_image_array_by_annotation = {
        "a1": np.array([[True, False], [True, True]]),
        "a2": np.array([[False, True], [True, False]]),
    }

    expected_output1 = {"a1": np.array([[True, False], [False, True]]), "a2": np.array([[False, True], [True, False]])}
    actual_output1 = remove_overlap_of_binary_image_array(binary_image_array_by_annotation, ["a1", "a2"])
    for annotation_id in ["a1", "a2"]:
        np.testing.assert_array_equal(actual_output1[annotation_id], expected_output1[annotation_id])

    expected_output2 = {"a1": np.array([[True, False], [True, True]]), "a2": np.array([[False, True], [False, False]])}
    actual_output2 = remove_overlap_of_binary_image_array(binary_image_array_by_annotation, ["a2", "a1"])
    for annotation_id in ["a1", "a2"]:
        np.testing.assert_array_equal(actual_output2[annotation_id], expected_output2[annotation_id])
