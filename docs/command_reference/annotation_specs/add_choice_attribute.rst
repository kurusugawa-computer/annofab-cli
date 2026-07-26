==========================================
annotation_specs add_choice_attribute
==========================================

Description
=================================
アノテーション仕様に選択肢系属性（ラジオボタン/ドロップダウン）を1件追加し、指定したラベルへ紐付けます。

選択肢情報をCSVで管理している場合に便利です。JSONで複数の属性をまとめて追加したい場合は :doc:`add_attributes` を使用してください。


Examples
=================================

JSON形式の例
----------------------------------------------

選択肢属性の初期値にしたい選択肢には ``is_default`` に ``true`` を指定します。

.. code-block:: json
    :caption: choices.json

    [
        {
            "choice_name_en": "front"
        },
        {
            "choice_id": "c2",
            "choice_name_en": "rear",
            "choice_name_ja": "後ろ",
            "is_default": true,
            "keybind": {
                "alt": false,
                "code": "Digit1",
                "ctrl": true,
                "shift": false
            }
        }
    ]


.. code-block::

    $ annofabcli annotation_specs add_choice_attribute \
     --project_id prj1 \
     --attribute_type choice \
     --attribute_name_en direction \
     --choice_json file://choices.json \
     --label_name_en car bus \


CSV形式の例
----------------------------------------------

.. code-block::
    :caption: choices.csv

    choice_id,choice_name_en,choice_name_ja,is_default,keybind
    ,front,,,
    c2,rear,後ろ,true,"{""alt"": false, ""code"": ""Digit1"", ""ctrl"": true, ""shift"": false}"


.. code-block::

    $ annofabcli annotation_specs add_choice_attribute \
     --project_id prj1 \
     --attribute_type select \
     --attribute_name_en direction \
     --choice_csv choices.csv \
     --label_id l1 l2


選択肢情報の構造
=================================

``--choice_json`` と ``--choice_csv`` には、追加する選択肢情報を指定します。JSONでは配列の各要素、CSVでは各行が1件の選択肢を表します。

選択肢情報では、以下の項目を指定できます。

* ``choice_name_en`` : 必須。選択肢名（英語）。
* ``choice_name_ja`` : 任意。選択肢名（日本語）。
* ``choice_id`` : 任意。選択肢ID。未指定の場合はUUIDv4が自動生成されます。
* ``is_default`` : 任意。 ``true`` を指定すると属性の初期値として使用します。未指定の場合は ``false`` です。
* ``keybind`` : 任意。選択肢に設定するキーボードショートカット。 ``code`` に指定できる値は、 `KeyboardEvent.code <https://developer.mozilla.org/ja/docs/Web/API/KeyboardEvent/code>`_ を参照してください。

選択肢は2件以上指定してください。
``choice_id`` は入力内で重複しない値を指定してください。
``is_default=true`` を指定できる選択肢は0件または1件です。


指定方法ごとの差分
=================================

* ``--choice_json`` : 追加する選択肢情報のJSON配列を指定します。 ``keybind`` にはJSONオブジェクトを指定してください。
* ``--choice_csv`` : 追加する選択肢情報のCSVファイルを指定します。 ``keybind`` 列にはJSONオブジェクト文字列を指定してください。


Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation_specs.add_choice_attribute.add_parser
    :prog: annofabcli annotation_specs add_choice_attribute
    :nosubcommands:
    :nodefaultconst:
