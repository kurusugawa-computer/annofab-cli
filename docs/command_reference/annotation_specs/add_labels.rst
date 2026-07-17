==========================================
annotation_specs add_labels
==========================================

Description
=================================
アノテーション仕様にラベルを複数件追加します。


Examples
=================================

ラベル名(英語)を複数指定する場合
----------------------------------------------

.. code-block::

    $ annofabcli annotation_specs add_labels \
     --project_id prj1 \
     --label_name_en pedestrian bicycle traffic_light \
     --annotation_type bounding_box



JSON形式で指定する場合
----------------------------------------------

.. code-block:: json
    :caption: labels.json

    [
        {
            "label_name_en": "pedestrian",
            "annotation_type": "bounding_box",
            "color": "#123456",
            "keybind": {
                "alt": false,
                "code": "Digit1",
                "ctrl": true,
                "shift": false
            },
            "field_values": {
                "display_name": {
                    "_type": "DisplayName",
                    "text": "歩行者"
                }
            }
        },
        {
            "label_id": "bicycle",
            "label_name_en": "bicycle",
            "label_name_ja": "自転車",
            "annotation_type": "bounding_box",
            "color": "#00AAFF"
        }
    ]


.. code-block::

    $ annofabcli annotation_specs add_labels \
     --project_id prj1 \
     --label_json file://labels.json


CSV形式で指定する場合
----------------------------------------------

.. code-block::
    :caption: labels.csv

    label_id,label_name_en,label_name_ja,annotation_type,color,keybind,field_values
    ,pedestrian,,segmentation_v2,#123456,"{""alt"": false, ""code"": ""Digit1"", ""ctrl"": true, ""shift"": false}","{""display_name"": {""_type"": ""DisplayName"", ""text"": ""歩行者""}}"
    bicycle,bicycle,自転車,segmentation_v2,#00AAFF,,


.. code-block::

    $ annofabcli annotation_specs add_labels \
     --project_id prj1 \
     --label_csv labels.csv

.. note::
    
    ``--annotation_type`` の値は、:doc:`add_label` を参照してください。 ``--label_name_en`` を使う場合は ``--annotation_type`` が必須です。
    ``--label_json`` / ``--label_csv`` を使う場合は、各ラベルに ``annotation_type`` を指定できます。 ``--annotation_type`` を併用した場合は、省略時の既定値として使われます。
    ラベル側の ``annotation_type`` と ``--annotation_type`` が不一致の場合はエラーになります。
    ``--label_json`` / ``--label_csv`` では ``keybind`` と ``field_values`` も指定できます。 ``--label_json`` では ``keybind`` と ``field_values`` にJSONオブジェクトを指定してください。
    ``--label_csv`` では ``keybind`` 列と ``field_values`` 列にJSONオブジェクト文字列を指定してください。APIの ``keybind`` は配列形式ですが、このコマンドでは画面と同じく1つだけ指定できます。
    ``field_values`` のフォーマットは、:doc:`update_label_field_values` を参照してください。


Usage Details
=================================



.. argparse::
    :ref: annofabcli.annotation_specs.add_labels.add_parser
    :prog: annofabcli annotation_specs add_labels
    :nosubcommands:
    :nodefaultconst:
