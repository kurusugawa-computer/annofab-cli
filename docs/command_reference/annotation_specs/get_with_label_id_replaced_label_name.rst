====================================================================================
annotation_specs get_with_label_id_replaced_label_name
====================================================================================

Description
=================================
label_idをUUIDから英語名に置換したアノテーション仕様のJSONを出力します。

アノテーション仕様は変更しません。画面のインポート機能を使って、アノテーション仕様を変更することを想定しています。

相関制約をJSONで直接設定する際などに利用すると便利です。IDをがUUID形式から分かりやすい名前になるため、JSON記述しやすくなります。

.. warning::

    既にアノテーションが存在する状態でlabel_idを変更すると、既存のアノテーション情報が消える恐れがあります。十分注意して、label_idを変更してください。



Examples
=================================

基本的な使い方
--------------------------


.. code-block::

    # 元のアノテーション仕様の最初のラベル情報を出力
    $ annofabcli annotation_specs list_label -p 58a2a621-7d4b-41e7-927b-cdc570c1114a -f pretty_json | jq  ".[0]"
    {
        "label_id": "8ec9417b-abef-47ad-af7d-e0a03c680eac",
        "label_name": {
            "messages": [
            {
                "lang": "ja-JP",
                "message": "天気"
            },
            {
                "lang": "en-US",
                "message": "weather"
            }
            ],
            "default_lang": "ja-JP"
        },
        ...
    }

    # label_idを英語名に変更したアノテーション仕様を出力
    $ annofabcli annotation_specs get_with_label_id_replaced_label_name --project_id prj1 --out out.json

    $ jq ".labels[0]" out.json
    {
        "label_id": "weather",
        "label_name": {
            "messages": [
            {
                "lang": "ja-JP",
                "message": "天気"
            },
            {
                "lang": "en-US",
                "message": "weather"
            }
            ],
            "default_lang": "ja-JP"
        },
        ...
    }



特定のラベルのlabel_idのみ変更する場合は、 ``--label_name`` を指定してください。

.. code-block::

    $ annofabcli annotation_specs get_with_label_id_replaced_label_name --project_id prj1 \
     --label_name weather car --out out.json




Usage Details
=================================

.. argparse::
   :ref: annofabcli.annotation_specs.get_annotation_specs_with_label_id_replaced.add_parser
   :prog: annofabcli annotation_specs get_with_label_id_replaced_label_name
   :nosubcommands:
   :nodefaultconst:
