---
name: pandas-conventions
description: pandasを使用するPythonコードの作成・修正・レビュー時に適用する、推奨コーディング規約。この規約は、LLMによるコード生成が期待通りでない場合に追記しています。規約だけでなく、AIに伝えたい情報も記載してあります。
---

## `pandas.DataFrame.to_dict()`
* `pandas.DataFrame.to_dict()`は`pd.NA`を`None`に変換します。またnumpyの数値型はpythonの数値型に変換します。したがって、`pandas.DataFrame.to_dict()`の結果に対して、`int()`や`pd.isna()`などの不要な処理は実施しないでください。

### `pandas.read_csv()`
* できる限りnullableなdtypeを使用してください。

* `pandas.read_csv()`で文字列として読み込む場合は、`dtype`を`str`でなく`string`として指定してください。欠損値を`NaN`ではなく`pd.NA`として扱いたいからです。

* `pandas.read_csv()`の`dtype`引数は、存在しない列を指定できます。
