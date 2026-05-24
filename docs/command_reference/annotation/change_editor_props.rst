====================================================================================
annotation change_editor_props
====================================================================================

Description
=================================
指定したラベル名のアノテーションの ``editor_props`` （削除禁止などのプロパティ）を一括で変更します。
作業中状態のタスクに含まれるアノテーションは変更できません。


Examples
=================================

基本的な使い方
--------------------------

``--task_id`` にアノテーション変更対象のタスクのtask_idを指定してください。

``--label_name`` には、変更対象のアノテーションのラベル名（英語）を指定してください。
複数のラベル名を指定できます。

``--editor_props`` に、変更後の ``editor_props`` をJSON形式で指定してください。
指定したキーだけ既存の ``editor_props`` にマージされます。

以下のコマンドは、ラベル名（英語）が ``car`` または ``road`` であるアノテーションに対して、 ``can_delete`` を ``false`` に変更します。

.. code-block::

    $ annofabcli annotation change_editor_props --project_id prj1 --task_id file://task.txt \
    --label_name car road \
    --editor_props '{"can_delete": false}' \
    --backup backup_dir/




``--backup`` にディレクトリを指定すると、変更対象の入力データに含まれるアノテーション情報を、バックアップとしてディレクトリに保存します。
アノテーション情報の復元は、 `annofabcli annotation restore <../annotation/restore.html>`_ コマンドで実現できます。


.. note::

    間違えてアノテーションの ``editor_props`` を変更したときに復元できるようにするため、``--backup`` を指定することを推奨します。


デフォルトでは完了状態のタスクに含まれるアノテーションは変更できません。完了状態のタスクに含まれるアノテーションも変更する場合は、 ``--include_complete_task`` を指定してください。
ただし、オーナーロールのユーザーで実行する必要があります。

デフォルトでは保留中状態のタスクに含まれるアノテーションも変更できません。保留中状態のタスクに含まれるアノテーションも変更する場合は、 ``--include_on_hold_task`` を指定してください。


.. _annotation_change_editor_props_editor_props_keys:

``editor_props`` に指定できるキー
----------------------------------------------------


*  ``can_delete`` ：アノテーションを削除できるかどうか（2026年5月時点では、動画エディタでは対応していません）
*  ``can_edit_data`` ：アノテーションのデータを編集できるかどうか（2026年5月時点では、画像エディタ、動画エディタでは対応していません）
*  ``can_edit_additional`` ：アノテーションの属性値を編集できるかどうか（2026年5月時点では、画像エディタ、動画エディタでは対応していません）


Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation.change_annotation_editor_props.add_parser
    :prog: annofabcli annotation change_editor_props
    :nosubcommands:
    :nodefaultconst:


See also
=================================
*  `annofabcli annotation restore <../annotation/restore.html>`_
