===================================
annotation change_attributes
===================================


Description
==========================

アノテーションの属性値を一括で変更します。
ただし、作業中状態のタスクのアノテーションは、属性値を変更できません。







Examples
==========================



基本的な使い方
--------------------------

``--task_id`` にアノテーション変更対象のタスクのtask_idを指定してください。
プロジェクト内の全タスクを対象にする場合は、代わりに ``--all_tasks`` を指定してください。
対象指定の詳細は :ref:`task-selection-for-updates` を参照してください。
全タスク取得が10,000件の上限に達した場合は、変更前に中断します。その場合は ``--task_id`` で対象を絞り込んでください。

``--annotation_query`` には、変更対象のアノテーションを検索するする条件をJSON形式で指定してください。
``--annotation_query`` のサンプルは、`Command line options <../../user_guide/command_line_options.html#annotation-query-aq>`_ を参照してください。


``--attributes`` に、変更後の属性値を指定してください。フォーマットは ``--annotation_query`` の ``attributes`` キーの値と同じフォーマットです。

以下のコマンドは、ラベル名（英語）の値が"car"であるアノテーションに対して、属性名(英語)が"occluded"である属性値をfalse（"occluded"チェックボックスをOFF）に変更します。

.. code-block::

    $ annofabcli annotation change_attributes --project_id prj1 --task_id file://task.txt \
    --annotation_query '{"label": "car"}' \
    --attributes '{"occluded": false}' \
    --backup backup_dir/

全タスクを対象にする場合の実行例です。

.. code-block::

    $ annofabcli annotation change_attributes --project_id prj1 --all_tasks \
    --annotation_query '{"label": "car"}' \
    --attributes '{"occluded": false}' \
    --backup backup_dir/

``--backup`` にディレクトリを指定すると、変更対象のタスクのアノテーション情報を、バックアップとしてディレクトリに保存します。
アノテーション情報の復元は、 `annofabcli annotation restore <../annotation/restore.html>`_ コマンドで実現できます。


.. note::

    間違えてアノテーション属性値を変更したときに復元できるようにするため、``--backup`` を指定することを推奨します。

デフォルトでは完了状態のタスクのアノテーション属性値は変更できません。完了状態のタスクのアノテーション属性値も変更する場合は、 ``--include_complete_task`` を指定してください。
ただし、オーナーロールであるユーザーで実行する必要があります。


保留中のタスクは、``--include_on_hold_task`` を指定した場合のみ変更します。
詳細は :ref:`include-on-hold-task-for-annotation-updates` を参照してください。


Usage Details
==========================


.. argparse::
    :ref: annofabcli.annotation.change_annotation_attributes.add_parser
    :prog: annofabcli annotation change_attributes
    :nosubcommands:
    :nodefaultconst:


See also
==========================

*  `annofabcli annotation restore <../annotation/restore.html>`_


終了コード
===================================

終了コードと処理継続の仕様は :ref:`batch-annotation-update-exit-code` を参照してください。
