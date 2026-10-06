==================================================
statistics
==================================================

Description
=================================
統計関係のコマンドです。

アノテーションの面積を取得する場合は、種類に応じて以下のコマンドを使用してください。
各コマンドは面積を ``area`` として出力します。

* 矩形: :doc:`../annotation_zip/list_bounding_box_annotation`
* ポリゴン: :doc:`../annotation_zip/list_polygon_annotation`
* 塗りつぶしv1/v2: :doc:`../annotation_zip/list_segmentation_annotation`


Available Commands
=================================


.. toctree::
   :maxdepth: 1
   :titlesonly:


   list_annotation_count
   list_annotation_duration
   list_video_duration
   list_worktime
   summarize_task_count_by_task_id_group
   summarize_task_count_by_user
   visualize
   visualize_annotation_count
   visualize_annotation_duration
   visualize_video_duration

Usage Details
=================================

.. argparse::
   :ref: annofabcli.statistics.subcommand_statistics.add_parser
   :prog: annofabcli statistics
   :nosubcommands:
