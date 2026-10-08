"""レポート出力用のユーザー情報のマスク処理。"""

from __future__ import annotations

import argparse
import hashlib
from dataclasses import dataclass, replace

import pandas
from pandas.api.types import is_string_dtype

from annofabcli.common.cli import get_list_from_args


def create_masked_name(value: str, *, prefix: str = "user") -> str:
    """入力値から安定した仮名を生成します。

    Args:
        value: マスクする文字列。
        prefix: 仮名の接頭辞。

    Returns:
        入力値と接頭辞が同じなら、ファイルや実行順によらず同じになる仮名。
    """
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _column(df: pandas.DataFrame, name: str) -> str | tuple[str, ...]:
    """ヘッダの段数に合わせた列名を返します。

    Args:
        df: 対象のDataFrame。
        name: 列名。

    Returns:
        単一ヘッダの列名、または複数行ヘッダの列名タプル。
    """
    return (name, *([""] * (df.columns.nlevels - 1))) if isinstance(df.columns, pandas.MultiIndex) else name


@dataclass(frozen=True)
class UserInfoMasker:
    """ユーザーIDを基準として、同一ユーザーのID・名前・アカウントIDを同じ仮名に置換します。"""

    not_masked_user_ids: frozenset[str] = frozenset()
    """マスクしないユーザーID。"""
    not_masked_biographies: frozenset[str] = frozenset()
    """マスクしないユーザーのbiography。"""

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> UserInfoMasker | None:
        """CLIオプションからマスク設定を生成します。

        Args:
            args: 生成コマンドのCLI引数。

        Returns:
            マスク設定。マスクが指定されていなければNone。
        """
        if not args.mask_user_info:
            return None
        return cls(
            not_masked_user_ids=frozenset(get_list_from_args(args.not_masked_user_id)) if args.not_masked_user_id is not None else frozenset(),
            not_masked_biographies=frozenset(get_list_from_args(args.not_masked_biography)) if args.not_masked_biography is not None else frozenset(),
        )

    def with_user_df(self, df: pandas.DataFrame) -> UserInfoMasker:
        """biographyによる除外をユーザーIDに解決します。

        Args:
            df: ユーザーIDとbiographyを含むDataFrame。

        Returns:
            biography列がないタスクやグラフにも同じ除外条件を適用できるマスク設定。
        """
        user_id_column = _column(df, "user_id")
        biography_column = _column(df, "biography")
        if not self.not_masked_biographies or user_id_column not in df or biography_column not in df:
            return self
        excluded_ids = df.loc[df[biography_column].astype("string").isin(self.not_masked_biographies), user_id_column].dropna().astype("string")
        return replace(self, not_masked_user_ids=self.not_masked_user_ids.union(excluded_ids))

    def mask_user_ids(self, user_ids: list[str] | None) -> list[str] | None:
        """グラフに表示するユーザーIDをマスク後のIDに変換します。

        Args:
            user_ids: 実IDによる表示対象の指定。

        Returns:
            マスク後の表示対象。未指定ならNone。
        """
        if user_ids is None:
            return None
        return [user_id if user_id in self.not_masked_user_ids else create_masked_name(user_id) for user_id in user_ids]

    def mask_dataframe(self, df: pandas.DataFrame) -> pandas.DataFrame:
        """ユーザー情報をマスクしたコピーを返します。

        Args:
            df: 単一または複数行ヘッダのレポート。タスクの各フェーズの初回作業者にも対応します。

        Returns:
            ユーザー情報を置換したDataFrame。欠損値・集計値・元のDataFrameは保持します。
        """
        result = df.copy()
        for prefix in ("", "first_annotation_", "first_inspection_", "first_acceptance_"):
            user_id_column = _column(df, f"{prefix}user_id")
            if user_id_column not in df:
                continue
            user_ids = df[user_id_column].astype("string")
            masked_rows = ~user_ids.isin(self.not_masked_user_ids)
            aliases = user_ids.map(create_masked_name, na_action="ignore")
            id_rows = masked_rows & user_ids.notna()
            if id_rows.any():
                if not is_string_dtype(result[user_id_column].dtype):
                    result[user_id_column] = df[user_id_column].astype("string")
                result.loc[id_rows, user_id_column] = aliases[id_rows]
            for name in ("username", "account_id"):
                column = _column(df, f"{prefix}{name}")
                if column not in df:
                    continue
                value_rows = masked_rows & df[column].notna()
                if not value_rows.any():
                    continue
                # IDが欠損していても、名前やアカウントIDをそのまま出力しない。
                values = aliases.where(user_ids.notna(), df[column].astype("string").map(create_masked_name, na_action="ignore"))
                if not is_string_dtype(result[column].dtype):
                    result[column] = df[column].astype("string")
                result.loc[value_rows, column] = values[value_rows]
            biography_column = _column(df, f"{prefix}biography")
            if biography_column in df:
                biography_rows = masked_rows & df[biography_column].notna()
                if not biography_rows.any():
                    continue
                values = df[biography_column].astype("string").map(lambda value: create_masked_name(value, prefix="category"), na_action="ignore")
                if not is_string_dtype(result[biography_column].dtype):
                    result[biography_column] = df[biography_column].astype("string")
                result.loc[biography_rows, biography_column] = values[biography_rows]
        return result


def add_mask_user_info_arguments(parser: argparse.ArgumentParser) -> None:
    """レポート生成コマンドにマスク用のオプションを追加します。

    Args:
        parser: オプションを追加するパーサー。

    Returns:
        None。
    """
    parser.add_argument("--mask_user_info", action="store_true", help="出力するCSVとグラフのユーザーID、ユーザー名、アカウントID、biographyをマスクします。")
    parser.add_argument("--not_masked_user_id", nargs="+", help="'--mask_user_info'指定時にマスクしないユーザーID。``file://`` を先頭に付けると一覧ファイルを指定できます。")
    parser.add_argument("--not_masked_biography", nargs="+", help="'--mask_user_info'指定時にマスクしないユーザーのbiography。``file://`` を先頭に付けると一覧ファイルを指定できます。")
