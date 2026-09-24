タスクメタデータを出力する
--------------------------------------------------

``--with_task_metadata`` を指定すると、タスクのメタデータをすべて出力します。

.. code-block::

    $ annofabcli annotation_zip count_annotation_by_label --project_id prj1 \
      --with_task_metadata --output out.csv

CSVでは ``task_id`` の直後に、すべてのタスクに存在するキーを ``task_metadata.<key>`` 形式の列として出力します。キーがタスクに存在しない場合、そのセルは空になります。

JSONでは、タスクのメタデータ全体を ``task_metadata`` オブジェクトに出力します。
