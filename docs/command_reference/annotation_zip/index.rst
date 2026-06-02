==================================================
annotation_zip
==================================================

Description
=================================
アノテーションZIPまたはそれを展開したディレクトリ関係のコマンドです。


Available Commands
=================================


.. toctree::
   :maxdepth: 1
   :titlesonly:

   count_annotation_by_attribute_value
   count_annotation_by_label
   filter
   list_3d_bounding_box_annotation
   list_bounding_box_annotation
   list_polygon_annotation
   list_polyline_annotation
   list_range_annotation
   list_single_point_annotation
   merge
   render


Usage Details
=================================

.. argparse::
   :ref: annofabcli.annotation_zip.subcommand_annotation_zip.add_parser
   :prog: annofabcli annotation_zip
   :nosubcommands:
