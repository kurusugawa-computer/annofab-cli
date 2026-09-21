=======================================================
annotation change_label_per_annotation
=======================================================

Description
=================================

各アノテーションのラベルを個別に変更します。
作業中状態のタスクに含まれるアノテーションは変更できません。

.. warning::

   変更後のラベルに存在しない属性は削除されます。


Examples
=================================

変更内容をJSON形式で指定する
---------------------------------------

引数 ``--json`` に、変更対象のアノテーション（ ``task_id`` 、 ``input_data_id`` 、 ``annotation_id`` ）と変更後の ``label_id`` または ``label_name`` を指定します。各レコードでどちらか一方を指定してください。
``label_name`` は英語名を指定します。同名ラベルが複数存在する場合はエラーになるため、その場合は ``label_id`` を指定してください。

.. code-block:: json
   :caption: annotations.json

   [
     {
       "task_id": "t1",
       "input_data_id": "i1",
       "annotation_id": "a1",
       "label_name": "car"
     }
   ]

.. code-block::

   $ annofabcli annotation change_label_per_annotation --project_id p1 \
     --json file://annotations.json \
     --backup backup_dir/


変更内容をCSVで指定する
---------------------------------------

引数 ``--csv`` に、変更対象のアノテーションと変更後のラベルが記載されたCSVファイルを指定します。

.. csv-table::
   :header: 列名,必須,備考

   task_id,Yes,
   input_data_id,Yes,
   annotation_id,Yes,
   label_id,Either,変更後ラベルのID。 ``label_name`` と排他的
   label_name,Either,変更後ラベルの英語名。 ``label_id`` と排他的

.. code-block::
   :caption: annotations.csv

   task_id,input_data_id,annotation_id,label_name
   t1,i1,a1,car

.. code-block::

   $ annofabcli annotation change_label_per_annotation --project_id p1 \
     --csv annotations.csv \
     --backup backup_dir/


その他のオプション
---------------------------------------

``--backup`` にディレクトリを指定すると、変更対象のフレームに含まれるアノテーション情報を、指定したディレクトリに保存します。アノテーション情報の復元は、 `annofabcli annotation restore <../annotation/restore.html>`_ コマンドで実現できます。

完了状態のタスクに含まれるアノテーションも変更するには、 ``--include_complete_task`` を指定してください。ただし、オーナーロールのユーザーで実行する必要があります。


Usage Details
=================================

.. argparse::
   :ref: annofabcli.annotation.change_annotation_label_per_annotation.add_parser
   :prog: annofabcli annotation change_label_per_annotation
   :nosubcommands:
   :nodefaultconst:
