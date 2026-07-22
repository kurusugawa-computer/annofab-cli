==========================================
annotation_specs update_attributes
==========================================

Description
=================================
アノテーション仕様の既存属性に設定された日本語名、キーバインド、 ``read_only`` 、 ``default_value`` を更新します。

``attribute_id`` 、属性名(英語)、属性種類、選択肢、所属先ラベルは既存アノテーションへの影響を避けるため更新できません。


Examples
=================================

JSON形式で指定する場合
----------------------------------------------

.. code-block:: json
    :caption: attributes.json

    [
        {
            "attribute_name_en": "comment",
            "attribute_name_ja": "コメント",
            "keybind": {
                "alt": false,
                "code": "Digit1",
                "ctrl": true,
                "shift": false
            },
            "read_only": false,
            "default_value": "確認済み"
        },
        {
            "attribute_id": "f12a0b59-dfce-4241-bb87-4b2c0259fc6f",
            "read_only": true,
            "default_value": true
        }
    ]


.. code-block::

    $ annofabcli annotation_specs update_attributes \
     --project_id prj1 \
     --attribute_json file://attributes.json


``--attribute_json`` には、属性更新情報のJSON配列を指定してください。配列の各要素が1件の属性に対応します。

.. list-table::
    :header-rows: 1

    * - キー
      - 必須
      - 説明
    * - ``attribute_id``
      - 条件付き必須
      - 更新対象属性の ``attribute_id`` 。 ``attribute_name_en`` とどちらか一方を指定してください。
    * - ``attribute_name_en``
      - 条件付き必須
      - 更新対象属性の英語名。 ``attribute_id`` とどちらか一方を指定してください。この値自体は更新されません。
    * - ``attribute_name_ja``
      - 任意
      - 更新後の属性日本語名。
    * - ``keybind``
      - 任意
      - 更新後のキーボードショートカットのJSONオブジェクト。 ``code`` に指定できる値は、 `KeyboardEvent.code <https://developer.mozilla.org/ja/docs/Web/API/KeyboardEvent/code>`_ を参照してください。
    * - ``read_only``
      - 任意
      - 更新後の読み込み専用設定。 ``true`` または ``false`` を指定してください。
    * - ``default_value``
      - 任意
      - 更新後の初期値。属性の種類が ``flag`` の場合は真偽値、 ``integer`` の場合は整数、その他の場合は文字列を指定してください。


CSV形式で指定する場合
----------------------------------------------

.. code-block::
    :caption: attributes.csv

    attribute_id,attribute_name_en,attribute_name_ja,keybind,read_only,default_value
    ,comment,コメント,"{""alt"": false, ""code"": ""Digit1"", ""ctrl"": true, ""shift"": false}",false,確認済み
    f12a0b59-dfce-4241-bb87-4b2c0259fc6f,,,,true,true


CSV形式では、 ``keybind`` 列だけはJSONオブジェクト文字列として指定してください。
そのため、CSVセル全体を ``"`` で囲み、JSON内の ``"`` は ``""`` のようにエスケープする必要があります。

.. code-block::

    $ annofabcli annotation_specs update_attributes \
     --project_id prj1 \
     --attribute_csv attributes.csv


Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation_specs.update_attributes.add_parser
    :prog: annofabcli annotation_specs update_attributes
    :nosubcommands:
    :nodefaultconst:
