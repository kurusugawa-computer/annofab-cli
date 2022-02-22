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


   list_annotation_count
   list_worktime
   summarize_task_count
   summarize_task_count_by_task_id_group
   summarize_task_count_by_user
   visualize
   visualize_annotation_count

Usage Details
=================================

.. argparse::
   :ref: annofabcli.statistics.subcommand_statistics.add_parser
   :prog: annofabcli statistics
   :nosubcommands:
