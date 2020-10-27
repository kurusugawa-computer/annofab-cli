import argparse
import logging
from functools import partial
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import numpy
import pandas

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import (
    AbstractCommandLineInterface,
    ArgumentParser,
    build_annofabapi_resource_and_login,
    get_list_from_args,
)
from annofabcli.common.exceptions import AnnofabCliException
from annofabcli.common.utils import read_multiheader_csv

logger = logging.getLogger(__name__)


ALPHABET_SIZE = 26
DIGIT = 2


def _create_uniqued_masked_name(masked_name_set: Set[str], masked_name: str) -> str:
    """
    マスクされたユニークな名前を返す。
    `masked_name_set` に含まれている名前なら、末尾に数字をつけて、ユニークにする。
    """
    if masked_name not in masked_name_set:
        masked_name_set.add(masked_name)
        return masked_name
    else:
        # 末尾に数字を付ける
        base_masked_name = masked_name[0:DIGIT]
        try:
            # 末尾が数字の場合(末尾の数字が２桁になると処理がおかしくなるけど、許容する）
            now_index = int(masked_name[-1])
        except ValueError:
            # 末尾が数字でない場合
            now_index = 0

        new_masked_name = base_masked_name + str(now_index + 1)
        return _create_uniqued_masked_name(masked_name_set, new_masked_name)


def _create_replaced_dict(name_set: Set[str]) -> Dict[str, str]:
    """
    keyがマスク対象の名前で、valueがマスクしたあとの名前であるdictを返します。

    Args:
        name_set:

    Returns:

    """
    replaced_dict = {}
    masked_name_set: Set[str] = set()
    for name in name_set:
        masked_name = create_masked_name(name)
        unique_masked_name = _create_uniqued_masked_name(masked_name_set, masked_name)
        replaced_dict[name] = unique_masked_name
    return replaced_dict


def create_replaced_biography_dict(name_set: Set[str]) -> Dict[str, str]:
    replaced_dict = {}
    masked_name_set: Set[str] = set()
    for name in name_set:
        masked_name = create_masked_name(name)
        unique_masked_name = _create_uniqued_masked_name(masked_name_set, masked_name)
        replaced_dict[name] = unique_masked_name
    return replaced_dict


def create_masked_name(name: str) -> str:
    """
    マスクされた名前を返す。
    AA,ABのように、26*26 パターンを返す
    """

    def _hash_str(value: str) -> int:
        hash_value = 7
        for c in value:
            # 64bit integer
            hash_value = (31 * hash_value + ord(c)) & 18446744073709551615
        return hash_value

    def _num2alpha(num):
        """
        1以上の整数を大文字アルファベットに変換する
        """
        if num <= ALPHABET_SIZE:
            return chr(64 + num)
        elif num % 26 == 0:
            return _num2alpha(num // ALPHABET_SIZE - 1) + chr(90)
        else:
            return _num2alpha(num // ALPHABET_SIZE) + chr(64 + num % ALPHABET_SIZE)

    SIZE = pow(ALPHABET_SIZE, DIGIT)
    hash_value = (_hash_str(name) % SIZE) + 1
    return _num2alpha(hash_value)


def get_replaced_user_id_set_from_biography(
    df: pandas.DataFrame, not_masked_location_set: Optional[Set[str]] = None
) -> Set[str]:
    if not_masked_location_set is None:
        filtered_df = df
    else:
        filtered_df = df[df["biography"].map(lambda e: e not in not_masked_location_set)]

    return set(filtered_df["user_id"])


def _get_header_row_count(df: pandas.DataFrame) -> int:
    if isinstance(df.columns, pandas.MultiIndex):
        return len(df.columns.levels)
    else:
        return 1


def _get_tuple_column(df: pandas.DataFrame, column: str) -> Union[str, Tuple]:
    size = _get_header_row_count(df)
    if size >= 2:
        return tuple([column] + [""] * (size - 1))
    else:
        return column


def replace_by_columns(df, replacement_dict: Dict[str, str], main_column: Any, sub_columns: Optional[List[Any]] = None):
    def _get_username(row, main_column: Any, sub_column: Any) -> str:
        if row[main_column] in replacement_dict:
            return replacement_dict[row[main_column]]
        else:
            return row[sub_column]

    if sub_columns is not None:
        for sub_column in sub_columns:
            get_username_func = partial(_get_username, main_column=main_column, sub_column=sub_column)
            df[sub_column] = df.apply(get_username_func, axis=1)

    # 列の型を合わせないとreplaceに失敗するため, dtypを確認する
    if df[main_column].dtype == numpy.dtype("object"):
        df[main_column] = df[main_column].replace(replacement_dict)


def get_masked_username_series(df: pandas.DataFrame, replace_dict_by_user_id: Dict[str, str]) -> pandas.Series:
    """
    マスク後のusernameのSeriesを返す
    """
    user_id_column = _get_tuple_column(df, "user_id")
    username_column = _get_tuple_column(df, "username")

    def _get_username(row) -> str:
        if row[user_id_column] in replace_dict_by_user_id:
            return replace_dict_by_user_id[row[user_id_column]]
        else:
            return row[username_column]

    return df.apply(_get_username, axis=1)


def get_masked_account_id(df: pandas.DataFrame, replace_dict_by_user_id: Dict[str, str]) -> pandas.Series:
    """
    マスク後のaccount_idのSeriesを返す
    """
    user_id_column = _get_tuple_column(df, "user_id")
    account_id_column = _get_tuple_column(df, "account_id")

    def _get_account_id(row) -> str:
        if row[user_id_column] in replace_dict_by_user_id:
            return replace_dict_by_user_id[row[user_id_column]]
        else:
            return row[account_id_column]

    return df.apply(_get_account_id, axis=1)


def get_replaced_biography_set(df: pandas.DataFrame, not_masked_location_set: Optional[Set[str]] = None) -> Set[str]:
    biography_set = set(df["biography"])
    if numpy.nan in biography_set:
        biography_set.remove(numpy.nan)

    if not_masked_location_set is None:
        return biography_set
    else:
        for not_masked_location in not_masked_location_set:
            if not_masked_location in biography_set:
                biography_set.remove(not_masked_location)

    return biography_set


def create_replacement_dict_by_user_id(
    df: pandas.DataFrame,
    not_masked_biography_set: Optional[Set[str]] = None,
    not_masked_user_id_set: Optional[Set[str]] = None,
) -> Dict[str, str]:
    """
    keyが置換対象のuser_id、valueが置換後のマスクされたuser_idであるdictを作成する。
    """
    if "biography" in df:
        replaced_user_id_set = get_replaced_user_id_set_from_biography(
            df, not_masked_location_set=not_masked_biography_set
        )
    else:
        replaced_user_id_set = set()
    if not_masked_user_id_set is not None:
        replaced_user_id_set = replaced_user_id_set - not_masked_user_id_set

    return _create_replaced_dict(replaced_user_id_set)


def create_replacement_dict_by_biography(
    df: pandas.DataFrame,
    not_masked_biography_set: Optional[Set[str]] = None,
) -> Dict[str, str]:
    """
    keyが置換対象のbiography、valueが置換後のマスクされた biography であるdictを作成する。
    """
    replaced_biography_set = get_replaced_biography_set(df, not_masked_location_set=not_masked_biography_set)
    tmp_replace_dict_by_biography = _create_replaced_dict(replaced_biography_set)
    return {key: f"category-{value}" for key, value in tmp_replace_dict_by_biography.items()}


def replace_user_info_by_user_id(df: pandas.DataFrame, replacement_dict_by_user_id: Dict[str, str]):
    """
    user_id, username, account_id 列を, マスクする。

    Args:
        df:
        replacement_dict_by_user_id: user_idの置換前と置換後を示したdict

    """
    sub_columns = []
    user_id_column = _get_tuple_column(df, "user_id")

    if "username" in df:
        username_column = _get_tuple_column(df, "username")
        sub_columns.append(username_column)
    if "account_id" in df:
        account_id_column = _get_tuple_column(df, "account_id")
        sub_columns.append(account_id_column)
    replace_by_columns(df, replacement_dict_by_user_id, main_column=user_id_column, sub_columns=sub_columns)


def create_masked_user_info_df(
    csv: Path,
    csv_header: int,
    not_masked_biography_set: Optional[Set[str]] = None,
    not_masked_user_id_set: Optional[Set[str]] = None,
) -> pandas.DataFrame:
    if csv_header == 1:
        df = pandas.read_csv(str(csv))
    else:
        df = read_multiheader_csv(str(csv), header_row_count=csv_header)

    if "user_id" not in df:
        raise AnnofabCliException(f"`user_id`列が存在しないため、ユーザ情報をマスクできません。")

    replacement_dict_by_user_id = create_replacement_dict_by_user_id(
        df, not_masked_biography_set=not_masked_biography_set, not_masked_user_id_set=not_masked_user_id_set
    )
    replace_user_info_by_user_id(df, replacement_dict_by_user_id)
    if "biography" in df:
        replacement_dict_by_biography = create_replacement_dict_by_biography(
            df, not_masked_biography_set=not_masked_biography_set
        )
        df["biography"] = df["biography"].replace(replacement_dict_by_biography)

    return df


class MaskUserInfo(AbstractCommandLineInterface):
    def main(self):
        args = self.args

        not_masked_biography_set = (
            set(get_list_from_args(args.not_masked_biography)) if args.not_masked_biography is not None else None
        )
        not_masked_user_id_set = (
            set(get_list_from_args(args.not_masked_user_id)) if args.not_masked_user_id is not None else None
        )

        df = create_masked_user_info_df(
            csv=args.csv,
            csv_header=args.csv_header,
            not_masked_biography_set=not_masked_biography_set,
            not_masked_user_id_set=not_masked_user_id_set,
        )
        self.print_csv(df)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    MaskUserInfo(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    parser.add_argument("--csv", type=Path, required=True, help="ユーザ情報が記載されたCSVファイルを指定してください。CSVには`user_id`列が必要です。")
    parser.add_argument(
        "--not_masked_biography",
        type=str,
        nargs="+",
        help="マスクしないユーザの`biography`を指定してください。",
    )
    parser.add_argument(
        "--not_masked_user_id",
        type=str,
        nargs="+",
        help="マスクしないユーザの`user_id`を指定してください。",
    )
    parser.add_argument("--csv_header", type=int, help="CSVのヘッダ行数", default=1)

    argument_parser.add_output()
    argument_parser.add_csv_format()

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "mask_user_info"
    subcommand_help = "CSVに記載されたユーザ情報をマスクします。"
    description = "CSVに記載されたユーザ情報をマスクします。CSVの`user_id`,`username`,`biography`,`account_id` 列をマスクします。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
