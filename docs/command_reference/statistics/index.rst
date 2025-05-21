==================================================
statistics
==================================================

Description
=================================
統計関係のコマンドです。


Available Commands
=================================


.. toctree::
   :maxdepth: 1
   :titlesonly:


   list_annotation_attribute
   list_annotation_attribute_filled_count
   list_annotation_count
   list_annotation_duration
   list_annotation_area
   list_video_duration
   list_worktime
   summarize_task_count
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
