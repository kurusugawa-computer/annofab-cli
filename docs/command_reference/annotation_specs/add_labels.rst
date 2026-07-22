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

``--label_json`` には、ラベル情報のJSON配列を指定してください。配列の各要素が1件のラベルに対応します。

.. list-table::
    :header-rows: 1

    * - キー
      - 必須
      - 説明
    * - ``label_name_en``
      - 必須
      - ラベルの英語名。
    * - ``annotation_type``
      - 条件付き必須
      - ラベルのアノテーション種類。省略した場合は ``--annotation_type`` の値が使われます。JSON側と ``--annotation_type`` の両方に指定した場合、値が一致している必要があります。指定できる値は :doc:`add_label` を参照してください。
    * - ``label_id``
      - 任意
      - ラベルID。省略した場合はUUIDv4を自動生成します。
    * - ``label_name_ja``
      - 任意
      - ラベルの日本語名。省略した場合は ``label_name_en`` と同じ値を使用します。
    * - ``color``
      - 任意
      - ラベルの色。 ``#RRGGBB`` 形式の16進数カラーコードを指定してください。省略した場合は自動設定されます。
    * - ``keybind``
      - 任意
      - ラベルに設定するキーボードショートカットのJSONオブジェクト。  ``code`` に指定できる値は、 `KeyboardEvent.code <https://developer.mozilla.org/ja/docs/Web/API/KeyboardEvent/code>`_ を参照してください。
    * - ``field_values``
      - 任意
      - ラベルに設定するサイズ制約や許容誤差範囲などのJSONオブジェクト。フォーマットは :doc:`update_label_field_values` を参照してください。



CSV形式で指定する場合
----------------------------------------------

.. code-block::
    :caption: labels.csv

    label_id,label_name_en,label_name_ja,annotation_type,color,keybind,field_values
    ,pedestrian,,segmentation_v2,#123456,"{""alt"": false, ""code"": ""Digit1"", ""ctrl"": true, ""shift"": false}","{""margin_of_error_tolerance"": {""max_pixel"": 5, ""_type"": ""MarginOfErrorTolerance""}}"
    bicycle,bicycle,自転車,segmentation_v2,#00AAFF,,


CSV形式では、 ``keybind`` 列と ``field_values`` 列だけはJSONオブジェクト文字列として指定してください。
そのため、CSVセル全体を ``"`` で囲み、JSON内の ``"`` は ``""`` のようにエスケープする必要があります。

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
