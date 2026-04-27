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

.. code-block:: json
    :caption: field_values.json

    {
        "display_name": {
            "_type": "DisplayName",
            "text": "共通表示名"
        }
    }

.. code-block::

    $ annofabcli annotation_specs add_labels \
     --project_id prj1 \
     --label_name_en pedestrian bicycle traffic_light \
     --annotation_type bounding_box \
     --field_values_json file://field_values.json


ファイルからラベル名(英語)一覧を読み込む場合
----------------------------------------------

.. code-block::

    $ annofabcli annotation_specs add_labels \
     --project_id prj1 \
     --label_name_en file://label_names.txt \
     --annotation_type segmentation_v2


JSON形式で指定する場合
----------------------------------------------

.. code-block:: json
    :caption: labels.json

    [
        {
            "label_name_en": "pedestrian",
            "color": "#123456",
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
            "color": "#00AAFF"
        }
    ]


.. code-block::

    $ annofabcli annotation_specs add_labels \
     --project_id prj1 \
     --label_json file://labels.json \
     --annotation_type bounding_box


CSV形式で指定する場合
----------------------------------------------

.. code-block::
    :caption: labels.csv

    label_id,label_name_en,label_name_ja,color,field_values
    ,pedestrian,,#123456,"{""display_name"": {""_type"": ""DisplayName"", ""text"": ""歩行者""}}"
    bicycle,bicycle,自転車,#00AAFF


.. code-block::

    $ annofabcli annotation_specs add_labels \
     --project_id prj1 \
     --label_csv labels.csv \
     --annotation_type segmentation_v2


Usage Details
=================================

``--label_name_en`` , ``--label_json`` , ``--label_csv`` のいずれかを指定してください。
``--label_json`` / ``--label_csv`` では ``label_name_en`` は必須です。 ``label_id`` , ``label_name_ja`` , ``color`` , ``field_values`` は任意です。
``color`` には ``#RRGGBB`` 形式の16進数カラーコードを指定できます。
``--field_values_json`` を指定すると、追加する全ラベルに同じ ``field_values`` を設定できます。各ラベル個別の ``field_values`` と同時には指定できません。

``field_values`` のフォーマットは、 :doc:`update_label_field_values` を参照してください。

``--annotation_type`` の値は、``annotation_specs add_label`` の :ref:`annotation_specs_add_label_annotation_type_values` を参照してください。

.. argparse::
    :ref: annofabcli.annotation_specs.add_labels.add_parser
    :prog: annofabcli annotation_specs add_labels
    :nosubcommands:
    :nodefaultconst:
