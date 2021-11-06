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

``--input`` に，コピー元・コピー先となるタスクのtask_idを指定してください。
入力データは、タスク内の順序に対応しています。
たとえば上記のコマンドだと、「from_taskの1番目の入力データのアノテーション」を「to_taskの1番目の入力データ」にコピーします。

.. code-block::

    annofabcli annotation copy -p prj1 --input from_task_id:to_task_id 

アノテーション単位でコピーすることも可能です．

.. code-block::

    annofabcli annotation copy -p prj1 --input from_task_id/from_annotation_id:to_task_id/to_annotation_id 


ファイルを入力として指定することもできます．その場合，以下のような形式で入力してください．
入力は複数行にわたって指定することもできます．
.. code-block::

    annofabcli annotation copy -p prj1 --input file://task.txt 

.. code-block::
    :caption: task.txt

    from_task_id:to_task_id
    from_task_id/from_annotation_id:to_task_id/to_annotation_id


デフォルトでは、コピー先にすでにアノテーションが存在する場合はスキップします。
コピー元に含まれていないコピー先のアノテーションを残してコピーする場合は、 ``--merge`` を指定してください。
コピー先のアノテーションのannotation_idが、コピー元のアノテーションのannotation_idに一致すればアノテーションを上書きします。一致しなければアノテーションを追加します。

.. code-block::

    annofabcli annotaticn copy -p prj1 --merge --input from_task_id:to_task_id 

コピー先のアノテーションを削除してからインポートする場合は、 ``--overwrite`` を指定してください。

.. code-block::

    annofabcli annotation copy -p prj1 --overwrite --input from_task_id:to_task_id 

デフォルトでは以下のタスクに対しては、アノテーションのインポートをスキップします。

* タスクの担当者が自分自身でない
* タスクに担当者が割れ当てられたことがある

``--force`` を指定すると、担当者を自分自身に変更した上で、アノテーションをコピーすることができます。

コピー先のタスクが自分に割り当てられていない場合にforceオプションを指定すると，タスク割り当てを自分に変更してコピーします．

Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation.copy_annotation.add_parser
    :prog: annofabcli annotation copy
    :nosubcommands:
