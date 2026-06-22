==================================================
annotation
==================================================

Description
=================================
アノテーション関係のコマンドです。


Available Commands
=================================


.. toctree::
   :maxdepth: 1
   :titlesonly:

   change_attributes
   change_attributes_per_annotation
   change_data_per_annotation
   change_editor_props
   change_label
   copy
   create_classification
   delete
   delete_invalid_attribute_value
   download
   dump
   import
   list
   list_count
   merge_segmentation
   remove_segmentation_overlap
   restore

Usage Details
=================================

.. argparse::
   :ref: annofabcli.annotation.subcommand_annotation.add_parser
   :prog: annofabcli annotation
   :nosubcommands:
