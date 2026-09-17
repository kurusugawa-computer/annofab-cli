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
``--task_id`` を省略すると、プロジェクト内の全タスクを対象にします。
ただし、全タスク取得結果が10,000件以上の場合は、タスク一覧が打ち切られている可能性があるため処理を中断します。その場合は ``--task_id`` で対象タスクを絞り込んでください。

.. code-block::

    $ annofabcli annotation delete_invalid_label_annotation --project_id prj1 --task_id file://task.txt \
    --backup backup_dir/


プロジェクト内の全タスクを対象にする
----------------------------------

.. code-block::

    $ annofabcli annotation delete_invalid_label_annotation --project_id prj1 --backup backup_dir/


.. note::

    ``--task_id`` を省略したときに取得したタスク一覧が10,000件以上だった場合は、全件取得できていない可能性があるため処理を中断します。必要に応じて ``--task_id`` で対象タスクを絞り込んでください。


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
