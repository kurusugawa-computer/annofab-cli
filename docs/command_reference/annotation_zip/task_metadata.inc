タスクメタデータを出力する
--------------------------------------------------

``--task_metadata_key`` に出力したいメタデータのキーを指定できます。

.. code-block::

    $ annofabcli annotation_zip count_annotation_by_label --project_id prj1 \
      --task_metadata_key customer priority --output out.csv

CSVでは ``task_id`` の直後に ``task_metadata.customer`` 、
``task_metadata.priority`` のような列を出力します。キーがタスクに存在しない場合、そのセルは空になります。

JSONでは、指定したキーだけを ``task_metadata`` オブジェクトに出力します。
