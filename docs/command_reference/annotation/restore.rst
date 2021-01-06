==========================================
annotation restore
==========================================

Description
=================================
アノテーション情報をリストアします。
ただし、作業中または完了状態のタスクに対してはアノテーション情報をリストアできません。


Examples
=================================


基本的な使い方
--------------------------

``--annotation`` に、以下のいずれかのディレクトリパスを指定してください。

* `annofabcli annotation dump <../annotation/dump.html>`_ コマンドの出力先ディレクトリ
* `annofabcli annotation delete <../annotation/delete.html>`_ コマンドのバックアップ先ディレクトリ
* `annofabcli annotation change_attributes <../annotation/change_attributes.html>`_ コマンドのバックアップ先ディレクトリ

.. code-block::

    $ annofabcli annotation restore --project_id prj1 --annotation annotation.zip 


リストア対象のタスクを指定する場合は、``--task_id`` にリストア対象のタスクのtask_idを指定してください。

.. code-block::

    $ annofabcli annotation restore --project_id prj1 --annotation annotation.zip \
    --task_id file://task_id.txt



デフォルトでは以下のタスクに対しては、アノテーションのリストアをスキップします。

* タスクの担当者が自分自身でない
* タスクに担当者が割れ当てられたことがある

``--force`` を指定すると、担当者を一時的に自分自身に変更して、アノテーションをリストアすることができます。

.. code-block::

    $ annofabcli annotation restore --project_id prj1 --annotation annotation.zip \
    --force


See also
=================================
*  `annofabcli annotation dump <../annotation/restore.html>`_

