# アノテーション仕様を変更する際のガイドライン

## ショートカットキー
既存のショートカットキーと衝突しないようにするため、使用するキーは、キーボード上部1段目の数字キーと、キーボード上部2段目の`Q`~`P`に限定してください。
このキーに修飾キーを加えて、バリエーションを増やしてください。

## 英語名
ラベル、属性、選択肢の英語名は、アノテーションZIP内のJSONに出力されます。
したがって、アノテーションZIPを扱うスクリプトが扱いやすい名前にしてください。
たとえばスネークケースやキャメルケースにするなどです。


## ラベルの追加/変更

### ショートカットキー
ユーザーからの指示がなければ、ラベルにはキーボードショートカットを設定してください。
その際、できるだけラベルの順番とキーの順番が対応するようにしてください。

### `field_values`
https://annofab-cli.readthedocs.io/ja/latest/command_reference/annotation_specs/update_label_field_values.html#annotation-specs-field-values-samples を参照して、設定できる`field_values`があれば設定してください。

## 属性の追加/変更
* 属性を追加するには、先にラベルを追加する必要があります。

### 整数属性
* 小数を入力できません。小数を入力する場合は、属性の種類を「自由記述(1行)」にしてください。そして、正規表現による制約も設定してください。
* 未入力の場合、アノテーションZIPでは属性値が`0`になります。`0`と未入力を区別する必要があれば、属性の種類を「自由記述(1行)」にしてください。そして、正規表現による制約も設定してください。

### ラジオボタンとドロップダウンの使い分け
ドロップダウンとラジオボタンはどちらも「排他選択」で、アノテーションの出力結果は変わりません。アノテーションエディタ画面での入力方法が異なるだけです。
以下を考慮して、どちらにするかを決めてください。

* 任意入力か：ラジオボタンは一度選択すると未入力にできない。任意入力ならばドロップダウンにする。
* 選択肢に対してショートカットキーを設定するか？：ラジオボタンは選択肢に対して、ショートカットキーが設定可能。
* オートコンプリート：ドロップダウンは入力した文字列に部分一致した選択肢に絞り込むことができる。
* 選択肢の個数：選択肢が多ければドロップダウンがよい。





## 属性の制約の追加
* `annotation_specs add_attribute_restriction`コマンドに属性制約を表したJSONを指定して、アノテーション仕様に制約を追加します。
* 属性制約を表したJSONは、`annofabapi.util.attribute_restrictions`で生成してください。このライブラリを使うことで、使用できない制約（トラッキングID属性でのMatches（正規表現に一致する）など）のJSONを間違えて出力してしまうことを防げます。

```
>>> import annofabapi
>>> import json
>>> from annofabapi.util.attribute_restrictions import AttributeFactory
>>> service = annofabapi.build()
>>> annotation_specs, _ = service.api.get_annotation_specs("prj1", query_params={"v": "3"})

>>> fac = AttributeFactory(annotation_specs)

# 「'occluded'チェックボックスがONならば、'note'テキストボックスは空ではない」という制約
>>> restriction = fac.checkbox(attribute_name="occluded").checked().imply(fac.string_textbox(attribute_name="note").is_not_empty())

>>> print(json.dumps([restriction.to_dict()], ensure_ascii=False, indent=2))
[
  {
    "additional_data_definition_id": "9b05648d-1e16-4ea2-ab79-48907f5eed00",
    "condition": {
      "_type": "Imply",
      "premise": {
        "additional_data_definition_id": "2517f635-2269-4142-8ef4-16312b4cc9f7",
        "condition": {
          "_type": "Equals",
          "value": "true"
        }
      },
      "condition": {
        "_type": "NotEquals",
        "value": ""
      }
    }
  }
]
```

## オプションの変更
* 動画プロジェクトの場合は、`annotation_specs update_option`で`{"can_overwrap": false}`を指定すべきかを検討してください。
