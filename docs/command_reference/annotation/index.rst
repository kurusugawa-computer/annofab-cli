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
   change_properties
   copy
   delete
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
