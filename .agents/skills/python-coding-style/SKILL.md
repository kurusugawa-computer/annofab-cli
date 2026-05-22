---
name: python-coding-style
description: Pythonコードを作成・修正するときに使用。テストコードには適用されない。
---

# 全般
* できるだけ型ヒントを付ける。
    * できるだけ汎用的な型ヒントをつける。たとえばlistでもsetでも良いならば、`Collection`や`Iterable`を使う。
    * 特に理由がない限り、`object`や`Any`は避ける。
* docstring は Google スタイルで記述する。
* ログメッセージやコメントは日本語で記述する
* 戻り値をtupleで返そうとする場合は、`NamedTuple`, `dataclass`, pydantic modelの使用を検討して、本当にtupleが適切かどうかを判断する。
* モジュールレベルの定数、クラス属性、インスタンス属性などには直後に docstring として記述する。VSCodeのtooltipに表示させるため。

# pandas
* `pandas.DataFrame.to_dict()`は`pd.NA`を`None`に変換します。またnumpyの数値型はpythonの数値型に変換します。したがって、`pandas.DataFrame.to_dict()`の結果に対して、`int()`や`pd.isna()`などの不要な処理は実施しないでください。
