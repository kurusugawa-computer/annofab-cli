==========================================
annotation delete_invalid_label_annotation
==========================================

Description
=================================
アノテーション仕様に存在しないラベルを持つアノテーションを削除します。

アノテーションを付与した後に、アノテーション仕様画面でラベルを削除すると、Annofabのアノテーションエディタ画面にエラーアイコンが表示されます。
このエラーを解消するには、アノテーションエディタ画面で対象フレームを保存する必要があります。
ただし、対象フレームが多い場合、画面上で1件ずつ保存するのは手間がかかります。
そのような場合は、このコマンドを利用することで、アノテーション仕様に存在しないラベルを持つアノテーションを一括で削除できます。


Examples
=================================


基本的な使い方
--------------------------

``--task_id`` にアノテーション削除対象のタスクのtask_idを指定してください。

.. code-block::

    $ annofabcli annotation delete_invalid_label_annotation --project_id prj1 --task_id file://task.txt \
    --backup backup_dir/


``--backup`` にディレクトリを指定すると、変更対象のタスクのアノテーション情報を、バックアップとしてディレクトリに保存します。
アノテーション情報の復元は、 `annofabcli annotation restore <../annotation/restore.html>`_ コマンドで実現できます。

.. note::

    間違えてアノテーションを削除したときに復元できるようにするため、``--backup`` を指定することを推奨します。


.. note::

    作業中状態のタスクに含まれるアノテーションは削除できません。
    完了状態のタスクのアノテーションは、デフォルトでは削除できません。 ``--include_complete_task`` を指定すれば、完了状態のタスクに含まれるアノテーションも削除できます。ただし、``--include_complete_task`` はオーナーロールを持つユーザーでしか実行できません。


Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation.delete_invalid_label_annotation.add_parser
    :prog: annofabcli annotation delete_invalid_label_annotation
    :nosubcommands:
    :nodefaultconst:


See also
=================================
*  `annofabcli annotation restore <../annotation/restore.html>`_
