---
name: annofab-cli-user-operations
description: ユーザーからAnnofab上の情報取得やリソース操作を依頼されたときに使用します。操作にはannofabcliを使用してください。annofab-cli自体の開発には使用しません。
---

# annofab-cli-user-operations
ユーザーから依頼されたAnnofabの操作には、`annofabcli`を使用してください。

## コマンドの調べ方
- 使用するコマンドが明確でない場合は、[コマンド索引](references/command-index.md)を参照してください。
- コマンドを実行する前に`annofabcli <command> <subcommand> --help`を実行して、ヘルプを確認してください。コマンド名やオプションを推測しないでください。
- `--help`オプションのヘルプだけでは情報が不足している場合は、[ドキュメントのコマンドリファレンス](https://annofab-cli.readthedocs.io/ja/latest/command_reference/index.html)を参照してください。
- バージョンによって動作が異なる可能性がある場合は、`annofabcli --version`でインストール済みのバージョンを確認してください。

### 参考サイト
* [GitHubリポジトリ](https://github.com/kurusugawa-computer/annofab-cli)
* [Annofabのマニュアル](https://annofab.readme.io/docs/)

## リソースを変更するコマンド
* タスクやアノテーションなど、Annofab上のリソースを作成・更新・削除するコマンドは、ユーザーが操作を依頼した場合でも、実行前に確認を取ってください。
* 確認時は、対象のプロジェクトやリソース、実行する操作、設定内容を具体的に提示してください。内容を特定できない場合は、先に必要な情報を質問してください。
* ユーザーが提示した実行内容を確認して明示的に承認するまで、変更コマンドを実行しないでください。「作成してほしい」などの依頼だけでは、実行前確認への承認とみなしません。
* 承認された内容から対象や設定を変更する必要が生じた場合は、変更点を提示して改めて確認を取ってください。
* `--yes`オプションは、ユーザーがその使用を明示的に承認した場合に限り使用してください。
* リソースを変更した後は、可能であれば適切な読み取り専用コマンドで結果を確認してください。


## アノテーション仕様に関するコマンド
* `annotation import`などアノテーション関連のコマンドを実行する上で、アノテーション仕様のラベルと属性を参照する場合は、 `annotation_specs list_annotation_import_info`を使ってください。
* 属性を追加するには、先にラベルを追加する必要があります。

### 属性の制約の追加
* `annotation_specs add_attribute_constraint`コマンドに属性制約を表したJSONを指定して、アノテーション仕様に制約を追加します。
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

>>> print(json.dumps(restriction.to_dict())
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
```



## アノテーションの変更
`annotation create`などアノテーションを変更するコマンドを実行する場合は、以下のサイトを読み込んで、事前にアノテーションフォーマットを理解してください。

* [アノテーションJSONの詳細](https://annofab.readme.io/docs/annotation-format#detailsattributes)
* [画像プロジェクトのアノテーションJSON](https://annofab.readme.io/docs/image-annotation-format)
* [動画プロジェクトのアノテーションJSON](https://annofab.readme.io/docs/video-annotation-format)
* [3次元プロジェクトのアノテーションJSON](https://annofab.readme.io/docs/3dpc-annotation-format)
