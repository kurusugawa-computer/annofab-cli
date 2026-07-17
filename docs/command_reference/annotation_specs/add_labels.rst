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


``--annotation_type`` の値は、:doc:`add_label` を参照してください。 

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
                "margin_of_error_tolerance": {
                    "max_pixel": 5,
                    "_type": "MarginOfErrorTolerance"
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


``field_values`` のフォーマットは、:doc:`update_label_field_values` を参照してください。


CSV形式で指定する場合
----------------------------------------------

.. code-block::
    :caption: labels.csv

    label_id,label_name_en,label_name_ja,annotation_type,color,keybind,field_values
    ,pedestrian,,segmentation_v2,#123456,"{""alt"": false, ""code"": ""Digit1"", ""ctrl"": true, ""shift"": false}","{""margin_of_error_tolerance"": {""max_pixel"": 5, ""_type"": ""MarginOfErrorTolerance""}}"
    bicycle,bicycle,自転車,segmentation_v2,#00AAFF,,


.. code-block::

    $ annofabcli annotation_specs add_labels \
     --project_id prj1 \
     --label_csv labels.csv

    
    


Usage Details
=================================



.. argparse::
    :ref: annofabcli.annotation_specs.add_labels.add_parser
    :prog: annofabcli annotation_specs add_labels
    :nosubcommands:
    :nodefaultconst:
