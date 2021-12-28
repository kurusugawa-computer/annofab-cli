==========================================
annotation copy
==========================================

Description
=================================
アノテーションをコピーします．


Examples
=================================


基本的な使い方
--------------------------

``--input`` に、アノテーションのコピー元とコピー先を ``:`` で区切って指定してください。コピー元/コピー先は、タスク単位または入力データ単位で指定できます。


タスク単位でアノテーションをコピーする場合は、``--input`` にコピー元のtask_idとコピー先のtask_idを ``:`` で区切って指定してください。

.. code-block::

    $ annofabcli annotation copy -p prj1 --input src_task_id:dest_task_id 


``src_task_id`` のN番目の入力データに付与されているアノテーションが、``dest_task_id`` のN番目の入力データにコピーされます。
タスクに含まれる入力データ数が ``src_task_id`` と ``dest_task_id`` で異なる場合は、コピーできる入力データまで（ ``min(src_input_data.length, dest_input_data.length)`` 番目まで）コピーします。




入力データ単位でアノテーションをコピーする場合は、``--input`` にtask_idとinput_data_idを ``/`` で区切り、コピ元とコピー先を指定します。


.. code-block::

    $ annofabcli annotation copy -p prj1 --input src_task_id/src_input_data_id:dest_task_id/dest_input_data_id



コピー先ににアノテーションが存在する場合、デフォルトではアノテーションのコピーをスキップします。
コピー先のアノテーションを残した上でアノテーションをコピーする場合は、 ``--merge`` を指定してください。
コピー先のアノテーションのannotation_idが、コピー元のアノテーションのannotation_idに一致すればアノテーションを上書きします。一致しなければアノテーションを追加します。

.. code-block::

    $ annofabcli annotaticn copy -p prj1 --input src_task_id:dest_task_id --merge


コピー先のアノテーションを残さない場合は、 ``--overwrite`` を指定してください。

.. code-block::

    $ annofabcli annotation copy -p prj1 --input src_task_id:dest_task_id --overwrite


以下のタスクに対して、デフォルトではアノテーションのコピーをスキップします。

* タスクの担当者が自分自身でない
* タスクに担当者が割り当てられたことがある

``--force`` を指定すると、タスクの担当者が一時的に自分自身に変更され、アノテーションがコピーされます。

.. code-block::

    $ annofabcli annotation copy -p prj1 --input src_task_id:dest_task_id --force


Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation.copy_annotation.add_parser
    :prog: annofabcli annotation copy
    :nosubcommands:
    :nodefaultconst:
