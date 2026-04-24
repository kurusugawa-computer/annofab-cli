==========================================
annotation change_label
==========================================

Description
=================================

アノテーションのラベルを一括で変更します。
ただし、作業中状態のタスクに含まれるアノテーションは変更できません。
変更後ラベルに存在しない属性は削除されます。
また、変更前後のラベル種類が異なる場合はエラーになります。


Examples
=================================


基本的な使い方
--------------------------

``--annotation_query`` には、変更対象のアノテーションを検索する条件をJSON形式で指定してください。
``--annotation_query`` のサンプルは、`Command line options <../../user_guide/command_line_options.html#annotation-query-aq>`_ を参照してください。

変更後のラベルは、``--label_name`` または ``--label_id`` のいずれかで指定してください。

以下のコマンドは、ラベル名（英語）が ``car`` であるアノテーションを、ラベル名（英語）が ``bus`` であるラベルに変更します。

.. code-block::

    $ annofabcli annotation change_label --project_id prj1 --task_id file://task.txt \
    --annotation_query '{"label": "car"}' \
    --label_name bus \
    --backup backup_dir/

``--task_id`` を省略すると、プロジェクト内のすべてのタスクを対象にします。

.. code-block::

    $ annofabcli annotation change_label --project_id prj1 \
    --annotation_query '{"label": "car"}' \
    --label_id label_bus \
    --backup backup_dir/

``--backup`` にディレクトリを指定すると、変更対象のタスクのアノテーション情報を、バックアップとしてディレクトリに保存します。
アノテーション情報の復元は、 `annofabcli annotation restore <../annotation/restore.html>`_ コマンドで実現できます。


.. note::

    間違えてアノテーションラベルを変更したときに復元できるようにするため、``--backup`` を指定することを推奨します。

デフォルトでは完了状態のタスクのアノテーションラベルは変更できません。完了状態のタスクのアノテーションラベルも変更する場合は、 ``--include_complete_task`` を指定してください。
ただし、オーナーロールであるユーザーで実行する必要があります。


Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation.change_annotation_label.add_parser
    :prog: annofabcli annotation change_label
    :nosubcommands:
    :nodefaultconst:


See also
=================================
*  `annofabcli annotation restore <../annotation/restore.html>`_
