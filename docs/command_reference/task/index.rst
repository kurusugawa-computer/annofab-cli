==================================================
task
==================================================

Description
=================================
タスク関係のコマンドです。


Available Commands
=================================


.. toctree::
   :maxdepth: 1
   :titlesonly:

   accept
   cancel_acceptance
   change_operator
   change_status_to_break
   change_status_to_on_hold
   complete
   copy
   create
   create_by_input_data_count
   delete
   delete_metadata_key
   download
   list
   list_added_task_history
   list_all
   list_all_added_task_history
   list_video_duration
   put
   reject
   reject_with_inspection_comments
   submit
   update_input_data
   update_metadata
   update_metadata_per_task
   visualize_video_duration

Usage Details
=================================

.. argparse::
   :ref: annofabcli.task.subcommand_task.add_parser
   :prog: annofabcli task
   :nosubcommands:
