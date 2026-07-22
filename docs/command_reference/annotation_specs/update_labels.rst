==========================================
annotation_specs update_labels
==========================================

Description
=================================
アノテーション仕様の既存ラベルに設定された日本語名、色、キーバインド、 ``field_values`` を更新します。

``label_id`` 、ラベル名(英語)、アノテーション種類は既存アノテーションへの影響を避けるため更新できません。


Examples
=================================

JSON形式で指定する場合
----------------------------------------------

.. code-block:: json
    :caption: labels.json

    [
        {
            "label_name_en": "car",
            "label_name_ja": "車",
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
            "label_id": "bike",
            "field_values_operation": "replace"
        }
    ]


.. code-block::

    $ annofabcli annotation_specs update_labels \
     --project_id prj1 \
     --label_json file://labels.json


``field_values`` のフォーマットは、:doc:`update_label_field_values` を参照してください。

``--label_json`` には、ラベル更新情報のJSON配列を指定してください。配列の各要素が1件のラベルに対応します。

.. list-table::
    :header-rows: 1

    * - キー
      - 必須
      - 説明
    * - ``label_id``
      - 条件付き必須
      - 更新対象ラベルの ``label_id`` 。 ``label_name_en`` とどちらか一方を指定してください。
    * - ``label_name_en``
      - 条件付き必須
      - 更新対象ラベルの英語名。 ``label_id`` とどちらか一方を指定してください。この値自体は更新されません。
    * - ``label_name_ja``
      - 任意
      - 更新後のラベル日本語名。
    * - ``color``
      - 任意
      - 更新後のラベルの色。 ``#RRGGBB`` 形式の16進数カラーコードを指定してください。
    * - ``keybind``
      - 任意
      - 更新後のキーボードショートカットのJSONオブジェクト。 ``code`` に指定できる値は、 `KeyboardEvent.code <https://developer.mozilla.org/ja/docs/Web/API/KeyboardEvent/code>`_ を参照してください。
    * - ``field_values``
      - 任意
      - 更新するサイズ制約や許容誤差範囲などのJSONオブジェクト。 ``field_values_operation`` を省略した場合は既存の ``field_values`` にマージします。
    * - ``field_values_operation``
      - 任意
      - ``field_values`` の更新方法。 ``merge`` または ``replace`` を指定できます。 ``replace`` を指定して ``field_values`` を省略した場合は、 ``field_values`` を空辞書に更新します。


CSV形式で指定する場合
----------------------------------------------

.. code-block::
    :caption: labels.csv

    label_id,label_name_en,label_name_ja,color,keybind,field_values,field_values_operation
    ,car,車,#123456,"{""alt"": false, ""code"": ""Digit1"", ""ctrl"": true, ""shift"": false}","{""margin_of_error_tolerance"": {""max_pixel"": 5, ""_type"": ""MarginOfErrorTolerance""}}",
    bike,,,,,,replace


CSV形式では、 ``keybind`` 列と ``field_values`` 列だけはJSONオブジェクト文字列として指定してください。
そのため、CSVセル全体を ``"`` で囲み、JSON内の ``"`` は ``""`` のようにエスケープする必要があります。

.. code-block::

    $ annofabcli annotation_specs update_labels \
     --project_id prj1 \
     --label_csv labels.csv


Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation_specs.update_labels.add_parser
    :prog: annofabcli annotation_specs update_labels
    :nosubcommands:
    :nodefaultconst:
