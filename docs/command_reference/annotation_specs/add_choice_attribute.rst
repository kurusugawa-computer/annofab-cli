==========================================
annotation_specs add_choice_attribute
==========================================

Description
=================================
アノテーション仕様に選択肢系属性（ラジオボタン/ドロップダウン）を追加し、指定したラベルへ紐付けます。


Examples
=================================

JSON形式で指定する場合
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


CSV形式で指定する場合
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

読み込み専用の属性を追加する場合は、 ``--read_only`` を指定します。

属性本体の ``keybind`` を指定する場合は、 ``--keybind_json`` にJSONオブジェクトを指定してください。

選択肢の ``keybind`` を指定する場合は、 ``--choice_json`` ではJSONオブジェクト、 ``--choice_csv`` ではJSONオブジェクト文字列を指定してください。

.. code-block::

    $ annofabcli annotation_specs add_choice_attribute \
     --project_id prj1 \
     --attribute_type select \
     --attribute_name_en verified_direction \
     --choice_csv choices.csv \
     --read_only \
     --label_id l1 l2


Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation_specs.add_choice_attribute.add_parser
    :prog: annofabcli annotation_specs add_choice_attribute
    :nosubcommands:
    :nodefaultconst:
