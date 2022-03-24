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
   complete
   copy
   delete
   list
   list_with_json
   list_added_task_history
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
