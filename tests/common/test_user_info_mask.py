import pandas
import pytest
from pandas.testing import assert_frame_equal

from annofabcli.common.user_info_mask import UserInfoMasker, create_masked_name


@pytest.mark.parametrize("header_rows", [1, 2, 3])
def test_mask_dataframe_preserves_values_and_source(header_rows):
    original = pandas.DataFrame(
        {
            "user_id": ["alice", "bob", "alice"],
            "username": ["Same Name", "Same Name", "Alice New Name"],
            "account_id": ["account-a", "account-b", "account-a"],
            "biography": ["Japan", "Japan", "Japan"],
            "task_count": [3, 5, 7],
        }
    )
    if header_rows > 1:
        original.columns = pandas.MultiIndex.from_tuples([(name, *([""] * (header_rows - 1))) for name in original.columns])
    source = original.copy()
    masker = UserInfoMasker()
    masked = masker.mask_dataframe(original)
    expected_ids = [create_masked_name("alice"), create_masked_name("bob"), create_masked_name("alice")]
    for name in ("user_id", "username", "account_id"):
        assert list(masked[name]) == expected_ids
    assert list(masked["biography"]) == [create_masked_name("Japan", prefix="category")] * 3
    assert masked["task_count"].equals(original["task_count"])
    assert_frame_equal(original, source)
    # ファイル内のユーザー集合と行順が異なっても、同じユーザーは同じ仮名になる。
    assert_frame_equal(masker.mask_dataframe(original.iloc[[2, 0]]), masked.iloc[[2, 0]])


def test_mask_dataframe_without_biography():
    original = pandas.DataFrame({"user_id": ["alice", "bob"], "username": ["Alice", "Bob"]})
    masked = UserInfoMasker().mask_dataframe(original)
    assert list(masked["user_id"]) == [create_masked_name("alice"), create_masked_name("bob")]
    assert masked["user_id"].equals(masked["username"])


def test_mask_dataframe_missing_user_id_values():
    original = pandas.DataFrame({"user_id": ["alice", None, None], "username": [None, "Bob", None], "biography": [None, "Japan", None]}, dtype="string")
    masked = UserInfoMasker().mask_dataframe(original)
    assert masked.isna().equals(original.isna())
    assert masked.loc[1, "username"] == create_masked_name("Bob")
    assert masked.loc[1, "biography"] == create_masked_name("Japan", prefix="category")


@pytest.mark.parametrize("header_rows", [1, 2, 3])
def test_mask_dataframe_excludes_biography_with_missing_user_id(header_rows):
    original = pandas.DataFrame(
        {
            "user_id": [None, None, None],
            "username": ["Alice", "Bob", "Chris"],
            "account_id": ["alice-account", "bob-account", "chris-account"],
            "biography": ["Japan", "U.S.", None],
            "task_count": [1, 2, 3],
        }
    )
    if header_rows > 1:
        original.columns = pandas.MultiIndex.from_tuples([(name, *([""] * (header_rows - 1))) for name in original.columns])
    source = original.copy()
    masker = UserInfoMasker(not_masked_biographies=frozenset({"Japan"})).with_user_df(original)
    masked = masker.mask_dataframe(original)

    assert_frame_equal(masked.iloc[:1], original.iloc[:1])
    assert list(masked["username"].iloc[1:]) == [create_masked_name("Bob"), create_masked_name("Chris")]
    assert list(masked["account_id"].iloc[1:]) == [create_masked_name("bob-account"), create_masked_name("chris-account")]
    biography_column = "biography" if header_rows == 1 else ("biography", *([""] * (header_rows - 1)))
    assert masked.iloc[1][biography_column] == create_masked_name("U.S.", prefix="category")
    assert masked.isna().equals(original.isna())
    assert masked["task_count"].equals(original["task_count"])
    assert_frame_equal(original, source)


def test_mask_dataframe_empty():
    original = pandas.DataFrame(columns=["user_id", "username", "account_id", "biography", "task_count"])
    assert_frame_equal(UserInfoMasker().mask_dataframe(original), original)


def test_mask_dataframe_numeric_user_info():
    original = pandas.DataFrame({"user_id": ["001", None], "username": [123, 456], "account_id": [789, 987], "biography": [10, 20]})
    masked = UserInfoMasker().mask_dataframe(original)
    assert masked.loc[0, "user_id"] == masked.loc[0, "username"] == masked.loc[0, "account_id"] == create_masked_name("001")
    assert masked.loc[1, "username"] == create_masked_name("456")
    assert masked.loc[0, "biography"] == create_masked_name("10", prefix="category")


def test_mask_dataframe_excludes_users_in_all_reports():
    users = pandas.DataFrame({"user_id": ["alice", "bob", "chris"], "username": ["Alice", "Bob", "Chris"], "biography": ["Japan", "U.S.", "U.S."]})
    masker = UserInfoMasker(not_masked_user_ids=frozenset({"bob"}), not_masked_biographies=frozenset({"Japan"})).with_user_df(users)
    masked = masker.mask_dataframe(users)
    assert_frame_equal(masked.iloc[:2], users.iloc[:2])
    assert masked.loc[2, "user_id"] == create_masked_name("chris")
    assert masked.loc[2, "biography"] == create_masked_name("U.S.", prefix="category")
    without_biography = users.drop(columns="biography")
    assert_frame_equal(masker.mask_dataframe(without_biography).iloc[:2], without_biography.iloc[:2])
    assert masker.mask_user_ids(["alice", "bob", "chris"]) == ["alice", "bob", create_masked_name("chris")]


def test_mask_dataframe_task_phase_users():
    original = pandas.DataFrame(
        {
            "task_id": ["task1"],
            "first_annotation_user_id": ["alice"],
            "first_annotation_username": ["Same Name"],
            "first_inspection_user_id": ["bob"],
            "first_inspection_username": ["Same Name"],
            "first_acceptance_user_id": ["chris"],
            "first_acceptance_username": ["Chris"],
        }
    )
    masked = UserInfoMasker(not_masked_user_ids=frozenset({"chris"})).mask_dataframe(original)
    assert masked.loc[0, "first_annotation_username"] == masked.loc[0, "first_annotation_user_id"] == create_masked_name("alice")
    assert masked.loc[0, "first_inspection_username"] == masked.loc[0, "first_inspection_user_id"] == create_masked_name("bob")
    assert masked.loc[0, "first_acceptance_username"] == "Chris"
    assert masked.loc[0, "first_acceptance_user_id"] == "chris"
    assert masked["task_id"].equals(original["task_id"])
