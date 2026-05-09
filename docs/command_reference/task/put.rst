=================================
task put
=================================

Description
=================================
タスクを作成します。

.. warning::

   このコマンドは非推奨です。代わりに :doc:`create` コマンドを使用してください。

   ``task put`` コマンドは2027年01月01日以降に廃止予定です。


詳細な使用方法は :doc:`create` コマンドのドキュメントを参照してください。
コマンドライン引数の使い方は概ね同じですが、 ``task put --csv`` は互換維持のため引き続きヘッダ行なしCSVを受け付けます。


Usage Details
=================================

.. argparse::
   :ref: annofabcli.task.put_tasks.add_parser
   :prog: annofabcli task put
   :nosubcommands:
   :nodefaultconst:
