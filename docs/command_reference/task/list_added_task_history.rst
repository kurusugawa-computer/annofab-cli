==========================================
task list_added_task_history
==========================================

Description
=================================
タスク一覧に、タスク履歴から取得した以下の情報を追加した一覧を、CSV形式で出力します。

* フェーズごとの作業時間
* 各フェーズの最初の担当者と開始日時
* 各フェーズの最後の担当者と開始日時

最初に教師付を開始した日時や担当者などを調べるのに利用できます。



Examples
=================================


基本的な使い方
--------------------------

以下のコマンドは、タスク全件ファイルとタスク履歴全件ファイルをダウンロードしてから、タスク一覧を出力します。

.. code-block::

    $ annofabcli task list_added_task_history --project_id prj1 --output task.csv


タスク全件ファイルを指定する場合は ``--task_json`` 、タスク履歴全件ファイルを指定する場合は ``--task_history_json`` を指定してください。

.. code-block::

    $ annofabcli task list_added_task_history --project_id prj1 --output task.csv \
    --task_json task.json --task_history_json task_history.json

タスク全件ファイルやタスク履歴全件ファイルは、`annofabcli project download <../project/download.html>`_ コマンドでダウンロードできます。


タスクの絞り込み
----------------------------------------------

``--task_query`` 、 ``--task_id`` で、タスクを絞り込むことができます。


.. code-block::

    $ annofabcli task list_added_task_history --project_id prj1 \
     --task_query '{"status":"complete", "phase":"not_started"}'

    $ annofabcli task list_added_task_history --project_id prj1 \
     --task_id file://task_id.txt





出力結果
=================================
`annofabcli task list <../task/list.html>`_ コマンドの出力結果と同じです。


CSV出力
----------------------------------------------

.. code-block::

    $ annofabcli task list_added_task_history --project_id prj1 --output out.csv



出力結果 `out.csv <https://github.com/kurusugawa-computer/annofab-cli/blob/master/docs/command_reference/task/list_added_task_history/out.csv>`_ は、
`annofabcli task list_with_json <../task/list_with_json.html>`_ コマンドで出力されるCSVファイルと比較して、以下の情報（列）が追加されています。




* annotation_worktime_hour: 教師付フェーズの作業時間[hour]
* inspection_worktime_hour: 検査フェーズの作業時間[hour]
* acceptance_worktime_hour: 受入フェーズの作業時間[hour]
* first_annotation_user_id: 最初の教師付フェーズを担当したユーザのuser_id
* first_annotation_username: 最初の教師付フェーズを担当したユーザの名前
* first_annotation_started_datetime: 最初の教師付フェーズを開始した日時
* ...
* last_acceptance_user_id: 最後の受入フェーズを担当したユーザのuser_id
* last_acceptance_username: 最後の受入フェーズを担当したユーザの名前
* last_acceptance_started_datetime: 最後の受入フェーズを開始した日時




See also
=================================
* `annofabcli project download <../project/download.html>`_
* `annofabcli task list <../task/list.html>`_
* `annofabcli task list_with_json <../task/list_with_json.html>`_