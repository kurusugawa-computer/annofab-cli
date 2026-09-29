==================================================
annotation_zip
==================================================

Description
=================================
アノテーションZIPまたはそれを展開したディレクトリ関係のコマンドです。


名称を日本語名で出力する
=================================

一覧、集計、可視化を行うコマンドで ``--use_japanese_name`` を指定すると、ラベル名、属性名、選択肢名をアノテーション仕様に登録されている日本語名で出力します。
日本語名が登録されていない名称は、英語名のまま出力します。 ``--label_name`` や ``--attribute_name`` などの絞り込み条件には、従来どおり英語名を指定してください。

CSV形式で出力する例です。

.. code-block:: bash

    $ annofabcli annotation_zip list_annotation_attribute \
        --project_id prj1 --use_japanese_name --output out.csv

.. csv-table:: out.csv
   :file: use_japanese_name.csv
   :header-rows: 1

JSON形式で出力する例です。

.. code-block:: bash

    $ annofabcli annotation_zip count_annotation_by_attribute_value \
        --project_id prj1 --use_japanese_name --format pretty_json --output out.json

.. code-block:: json

    [
      {
        "annotation_count_by_attribute_value": {
          "車": {
            "種類": {
              "セダン": 10
            }
          }
        }
      }
    ]


Available Commands
=================================


.. toctree::
   :maxdepth: 1
   :titlesonly:

   count_annotation_attribute_filled
   count_annotation_by_attribute_value
   count_annotation_by_label
   filter
   list_3d_bounding_box_annotation
   list_3d_segment_annotation
   list_annotation_attribute
   list_bounding_box_annotation
   list_classification_annotation
   list_polygon_annotation
   list_polyline_annotation
   list_range_annotation
   list_segmentation_annotation
   list_single_point_annotation
   merge
   render
   visualize_annotation_count_by_attribute_value
   visualize_annotation_count_by_label


Usage Details
=================================

.. argparse::
   :ref: annofabcli.annotation_zip.subcommand_annotation_zip.add_parser
   :prog: annofabcli annotation_zip
   :nosubcommands:
