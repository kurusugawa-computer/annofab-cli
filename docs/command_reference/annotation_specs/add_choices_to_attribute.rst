==========================================
annotation_specs add_choices_to_attribute
==========================================

Description
=================================
既存の選択肢系属性（ラジオボタン/ドロップダウン）に、選択肢を追加します。


Examples
=================================

JSON形式の例
----------------------------------------------

.. code-block:: json
    :caption: choices.json

    [
        {
            "choice_name_en": "xlarge"
        },
        {
            "choice_id": "c2",
            "choice_name_en": "tiny",
            "choice_name_ja": "極小",
            "keybind": {
                "alt": false,
                "code": "Digit1",
                "ctrl": true,
                "shift": false
            }
        }
    ]


.. code-block::

    $ annofabcli annotation_specs add_choices_to_attribute \
     --project_id prj1 \
     --attribute_name_en type \
     --choice_json file://choices.json


CSV形式の例
----------------------------------------------

.. code-block::
    :caption: choices.csv

    choice_id,choice_name_en,choice_name_ja,keybind
    ,xlarge,,
    c2,tiny,極小,"{""alt"": false, ""code"": ""Digit1"", ""ctrl"": true, ""shift"": false}"


.. code-block::

    $ annofabcli annotation_specs add_choices_to_attribute \
     --project_id prj1 \
     --attribute_id 71620647-98cf-48ad-b43b-4af425a24f32 \
     --choice_csv choices.csv



選択肢情報の構造
=================================

``--choice_json`` と ``--choice_csv`` には、追加する選択肢情報を指定します。JSONでは配列の各要素、CSVでは各行が1件の選択肢を表します。

選択肢情報では、以下の項目を指定できます。

* ``choice_name_en`` : 必須。選択肢名（英語）。
* ``choice_name_ja`` : 任意。選択肢名（日本語）。
* ``choice_id`` : 任意。選択肢ID。未指定の場合はUUIDv4が自動生成されます。
* ``keybind`` : 任意。選択肢に設定するキーボードショートカット。 ``code`` に指定できる値は、 `KeyboardEvent.code <https://developer.mozilla.org/ja/docs/Web/API/KeyboardEvent/code>`_ を参照してください。

``choice_id`` と ``choice_name_en`` は、追加先の属性に既に存在する選択肢と重複しない値を指定してください。


指定方法ごとの差分
=================================

* ``--choice_json`` : 追加する選択肢情報のJSON配列を指定します。 ``keybind`` にはJSONオブジェクトを指定してください。
* ``--choice_csv`` : 追加する選択肢情報のCSVファイルを指定します。 ``keybind`` 列にはJSONオブジェクト文字列を指定してください。


Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation_specs.add_choices_to_attribute.add_parser
    :prog: annofabcli annotation_specs add_choices_to_attribute
    :nosubcommands:
    :nodefaultconst:
