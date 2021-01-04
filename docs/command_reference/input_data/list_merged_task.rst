==========================================
input_data list_merged_task
==========================================

Description
=================================
入力データ一覧にタスク一覧結合した一覧のCSVを出力します。
動画プロジェクトで、各タスクの動画時間を出力するときなどに利用できます。



Examples
=================================

基本的な使い方
--------------------------


以下のコマンドは、入力データ全件ファイル、タスク全件ファイルをダウンロードしてから、一覧を出力します。

.. code-block::

    $ annofabcli input_data list_merged_task --project_id prj1 


手元にある入力データ全件ファイル、タスク全件ファイルを指定する場合は、``--task_json`` , ``--input_data_json`` を指定してください。

.. code-block::

    $ annofabcli input_data list_merged_task --input_data_json input_data.json --task_json task.json


絞り込み
--------------------------

``--input_data_query`` を指定すると、入力データの名前や入力データのパスで絞り込めます。


以下のコマンドは、入力データ名に"sample"を含む一覧を出力します。

.. code-block::

    $ annofabcli input_data list_merged_task --project_id prj1  \
     --input_data_query '{"input_data_name": "sample"}' 



``--input_data_id`` を指定すると、input_data_idに合致する入力データの一覧を出力します。

.. code-block::

    $ annofabcli input_data list_merged_task --project_id prj1 \
     --input_data_id file://input_data_id.txt


出力結果
=================================


.. code-block::

    $ annofabcli input_data list_merged_task --project_id prj1 --output out.csv

`out.csv <https://github.com/kurusugawa-computer/annofab-cli/blob/master/docs/command_reference/input_data/list_merged_task/out.csv>`_



