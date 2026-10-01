==============
task complete
==============

.. warning::

   ``annofabcli task complete`` は非推奨です。2027/01/01に廃止予定です。
   教師付フェーズのタスクには :doc:`submit` を、検査または受入フェーズのタスクには :doc:`accept` を使用してください。

Description
=================================
教師付フェーズのタスクを提出し、検査または受入フェーズのタスクを合格にして、次のフェーズに進めます。
本コマンドは移行期間中の互換性のために提供しています。

Examples
=================================

教師付フェーズのタスクを提出します。

.. code-block::

    $ annofabcli task complete --project_id prj1 --task_id file://task_id.txt --phase annotation

検査または受入フェーズのタスクを合格にします。

.. code-block::

    $ annofabcli task complete --project_id prj1 --task_id file://task_id.txt --phase inspection

移行後のコマンドと使用方法は、以下を参照してください。

* :doc:`submit`
* :doc:`accept`

Usage Details
=================================

.. argparse::
   :ref: annofabcli.task.complete_tasks.add_complete_parser
   :prog: annofabcli task complete
   :nosubcommands:
   :nodefaultconst:
