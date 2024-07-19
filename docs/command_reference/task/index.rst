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

   cancel_acceptance
   change_operator
   change_status_to_break
   change_status_to_on_hold
   complete
   copy
   delete
   delete_metadata_key
   download
   list
   list_added_task_history
   list_all
   list_all_added_task_history
   put
   put_by_count
   reject
   update_metadata

Usage Details
=================================

.. argparse::
   :ref: annofabcli.task.subcommand_task.add_parser
   :prog: annofabcli task
   :nosubcommands:
