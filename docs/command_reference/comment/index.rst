==================================================
comment
==================================================

Description
=================================
コメント関係のコマンドです。


Available Commands
=================================


.. toctree::
   :maxdepth: 1
   :titlesonly:

   create_inspection
   create_inspection_simply
   create_onhold
   create_onhold_simply
   delete
   download
   list
   list_all
   list_all_with_replies
   list_with_replies
   put_inspection
   put_inspection_simply
   put_onhold
   put_onhold_simply
   update_inspection
   update_onhold

Usage Details
=================================

.. argparse::
   :ref: annofabcli.comment.subcommand_comment.add_parser
   :prog: annofabcli comment
   :nosubcommands:
