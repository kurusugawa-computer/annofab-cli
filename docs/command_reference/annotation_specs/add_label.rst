==========================================
annotation_specs add_label
==========================================

Description
=================================
アノテーション仕様にラベルを1件追加します。


Examples
=================================

基本的な使い方
----------------------------------------------

.. code-block::

    $ annofabcli annotation_specs add_label \
     --project_id prj1 \
     --label_name_en pedestrian \
     --annotation_type bounding_box


色やlabel_idを明示する場合
----------------------------------------------

.. code-block::

    $ annofabcli annotation_specs add_label \
     --project_id prj1 \
     --label_name_en road \
     --label_name_ja 路面 \
     --label_name_vi "mặt đường" \
     --annotation_type segmentation_v2 \
     --label_id road_label \
     --color '#00CCFF'


``field_values`` を指定して追加する場合
----------------------------------------------

.. code-block:: json
    :caption: field_values.json

    {
        "margin_of_error_tolerance": {
            "max_pixel": 5,
            "_type": "MarginOfErrorTolerance"
        }
    }


.. code-block::

    $ annofabcli annotation_specs add_label \
     --project_id prj1 \
     --label_name_en pedestrian \
     --annotation_type bounding_box \
     --field_values_json file://field_values.json


``field_values`` のフォーマットは、 :doc:`update_label_field_values` を参照してください。


``keybind`` を指定して追加する場合
----------------------------------------------

.. code-block::

    $ annofabcli annotation_specs add_label \
     --project_id prj1 \
     --label_name_en pedestrian \
     --annotation_type bounding_box \
     --keybind_json '{"alt": false, "code": "Digit1", "ctrl": true, "shift": false}'

``--keybind_json`` にはJSONオブジェクトを指定してください。
``code`` に指定できる値は、 `KeyboardEvent.code <https://developer.mozilla.org/ja/docs/Web/API/KeyboardEvent/code>`_ を参照してください。


``--annotation_type`` の値
----------------------------------------------

.. list-table::
    :header-rows: 1

    * - 値
      - 説明
      - 使用できるプロジェクト
    * - ``bounding_box``
      - 矩形
      - 画像プロジェクト
    * - ``segmentation``
      - 塗りつぶし（インスタンスセグメンテーション用）
      - 画像プロジェクト
    * - ``segmentation_v2``
      - 塗りつぶしv2（セマンティックセグメンテーション用）
      - 画像プロジェクト
    * - ``polygon``
      - ポリゴン（閉じた頂点集合）
      - 画像プロジェクト
    * - ``polyline``
      - ポリライン（開いた頂点集合）
      - 画像プロジェクト
    * - ``point``
      - 点
      - 画像プロジェクト
    * - ``classification``
      - 全体分類
      - 画像プロジェクト、動画プロジェクト
    * - ``range``
      - 動画の区間
      - 動画プロジェクト
    * - ``custom``
      - カスタム
      - カスタムプロジェクト
    * - ``user_bounding_box``
      - 3次元のバウンディングボックス
      - 3次元プロジェクト
    * - ``user_instance_segment``
      - 3次元のインスタンスセグメント
      - 3次元プロジェクト
    * - ``user_semantic_segment``
      - 3次元のセマンティックセグメント
      - 3次元プロジェクト


追加位置の指定
=================================

``--before_label_name_en`` に既存ラベルの英語名を指定すると、そのラベルの直前に追加します。
未指定の場合は末尾に追加します。既存ラベル同士の相対的な順序は維持します。
基準ラベルが存在しない場合や、英語名が一意でない場合は更新全体をエラーにします。

.. code-block::

    $ annofabcli annotation_specs add_label \
     --project_id prj1 \
     --label_name_en pedestrian \
     --annotation_type bounding_box \
     --before_label_name_en car


Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation_specs.add_label.add_parser
    :prog: annofabcli annotation_specs add_label
    :nosubcommands:
    :nodefaultconst:
