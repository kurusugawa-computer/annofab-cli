import argparse
import logging
from pathlib import Path
from typing import Dict, Optional, Set, Tuple, Union

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
    if masked_name not in masked_name_set:
        return masked_name
    else:
        base_masked_name = masked_name[0:DIGIT]
        now_index = int(masked_name[DIGIT:]) if len(masked_name) > DIGIT else 0
        new_masked_name = base_masked_name + str(now_index + 1)
        return _create_uniqued_masked_name(masked_name_set, new_masked_name)


def create_replaced_dict(name_set: Set[str]) -> Dict[str, str]:
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


def get_masked_username(df: pandas.DataFrame, replace_dict_by_user_id: Dict[str, str]) -> pandas.Series:
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


def replate_user_info(
    df: pandas.DataFrame,
    not_masked_biography_set: Optional[Set[str]] = None,
    not_masked_user_id_set: Optional[Set[str]] = None,
) -> pandas.DataFrame:
    if "biography" in df:
        replaced_user_id_set = get_replaced_user_id_set_from_biography(
            df, not_masked_location_set=not_masked_biography_set
        )
    else:
        replaced_user_id_set = set()
    if not_masked_user_id_set is not None:
        replaced_user_id_set = replaced_user_id_set - not_masked_user_id_set

    replace_dict_by_user_id = create_replaced_dict(replaced_user_id_set)
    if "username" in df:
        df["username"] = get_masked_username(df, replace_dict_by_user_id=replace_dict_by_user_id)
    if "account_id" in df:
        df["account_id"] = get_masked_account_id(df, replace_dict_by_user_id=replace_dict_by_user_id)
    df["user_id"] = df["user_id"].replace(replace_dict_by_user_id)

    if "biography" in df:
        replaced_biography_set = get_replaced_biography_set(df, not_masked_location_set=not_masked_biography_set)
        tmp_replace_dict_by_biography = create_replaced_dict(replaced_biography_set)
        replace_dict_by_biography = {key: f"category-{value}" for key, value in tmp_replace_dict_by_biography.items()}
        df["biography"] = df["biography"].replace(replace_dict_by_biography)
    return df


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

    new_df = replate_user_info(
        df, not_masked_biography_set=not_masked_biography_set, not_masked_user_id_set=not_masked_user_id_set
    )
    return new_df


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
        "--not_masked_biography", type=str, nargs="+", help="マスクしないユーザの`biography`を指定してください。",
    )
    parser.add_argument(
        "--not_masked_user_id", type=str, nargs="+", help="マスクしないユーザの`user_id`を指定してください。",
    )
    parser.add_argument("--csv_header", type=int, help="CSVのヘッダ行数 (default:1)", default=1)

    argument_parser.add_output()
    argument_parser.add_csv_format()

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "mask_user_info"
    subcommand_help = "CSVに記載されたユーザ情報をマスクします。"
    description = "CSVに記載されたユーザ情報をマスクします。CSVの`user_id`,`username`,`biography`,`account_id` 列をマスクします。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
