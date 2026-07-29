==========================================
annotation_specs update_attributes
==========================================

Description
=================================
アノテーション仕様の既存属性に設定された英語名、日本語名、ベトナム語名、キーバインド、 ``read_only`` 、 ``default_value`` を更新します。
JSON形式では、既存選択肢の英語名、日本語名、ベトナム語名、ショートカットキーも同時に更新できます。

``attribute_id`` 、属性種類、選択肢の削除、選択肢の並び順、所属先ラベルは既存アノテーションへの影響を避けるため更新できません。


Examples
=================================

JSON形式で指定する場合
----------------------------------------------

.. code-block:: json
    :caption: attributes.json

    [
        {
            "attribute_id": "54fa5e97-6f88-49a4-aeb0-a91a15d11528",
            "attribute_name_en": "comment",
            "attribute_name_ja": "コメント",
            "attribute_name_vi": "bình luận",
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
        },
        {
            "attribute_id": "71620647-98cf-48ad-b43b-4af425a24f32",
            "attribute_name_ja": "種別",
            "choice_updates": [
                {
                    "choice_id": "08ec927c-18e6-4bba-837a-b16de7061580",
                    "choice_name_en": "large",
                    "choice_name_ja": "大",
                    "choice_name_vi": "lớn",
                    "keybind": {
                        "alt": false,
                        "code": "Digit2",
                        "ctrl": true,
                        "shift": false
                    }
                },
                {
                    "choice_id": "74691a87-7962-4fa9-ba52-7cc466ecd982",
                    "keybind": null
                }
            ]
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
      - 必須
      - 更新対象属性の ``attribute_id`` 。
    * - ``attribute_name_en``
      - 任意
      - 更新後の属性英語名。
    * - ``attribute_name_ja``
      - 任意
      - 更新後の属性日本語名。
    * - ``attribute_name_vi``
      - 任意
      - 更新後の属性ベトナム語名。
    * - ``keybind``
      - 任意
      - 更新後のキーボードショートカットのJSONオブジェクト。 ``code`` に指定できる値は、 `KeyboardEvent.code <https://developer.mozilla.org/ja/docs/Web/API/KeyboardEvent/code>`_ を参照してください。
    * - ``read_only``
      - 任意
      - 更新後の読み込み専用設定。 ``true`` または ``false`` を指定してください。
    * - ``default_value``
      - 任意
      - 更新後の初期値。属性の種類が ``flag`` の場合は真偽値、 ``integer`` の場合は整数、その他の場合は文字列を指定してください。
    * - ``choice_updates``
      - 任意
      - 既存選択肢の更新情報の配列。選択肢系属性でのみ指定できます。

``choice_updates`` には、既存選択肢の更新情報を指定してください。配列の各要素が1件の選択肢に対応します。

.. list-table::
    :header-rows: 1

    * - キー
      - 必須
      - 説明
    * - ``choice_id``
      - 必須
      - 更新対象選択肢の ``choice_id`` 。
    * - ``choice_name_en``
      - 任意
      - 更新後の選択肢英語名。
    * - ``choice_name_ja``
      - 任意
      - 更新後の選択肢日本語名。
    * - ``choice_name_vi``
      - 任意
      - 更新後の選択肢ベトナム語名。
    * - ``keybind``
      - 任意
      - 更新後のキーボードショートカットのJSONオブジェクト。 ``null`` を指定するとショートカットキーを解除します。 ``code`` に指定できる値は、 `KeyboardEvent.code <https://developer.mozilla.org/ja/docs/Web/API/KeyboardEvent/code>`_ を参照してください。


CSV形式で指定する場合
----------------------------------------------

.. code-block::
    :caption: attributes.csv

    attribute_id,attribute_name_en,attribute_name_ja,attribute_name_vi,keybind,read_only,default_value
    54fa5e97-6f88-49a4-aeb0-a91a15d11528,comment,コメント,bình luận,"{""alt"": false, ""code"": ""Digit1"", ""ctrl"": true, ""shift"": false}",false,確認済み
    f12a0b59-dfce-4241-bb87-4b2c0259fc6f,,,,,true,true


CSV形式では、 ``keybind`` 列だけはJSONオブジェクト文字列として指定してください。
そのため、CSVセル全体を ``"`` で囲み、JSON内の ``"`` は ``""`` のようにエスケープする必要があります。
CSV形式では選択肢情報は更新できません。選択肢情報も同時に更新したい場合はJSON形式を利用してください。

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
