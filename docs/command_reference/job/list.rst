=====================
job list
=====================

Description
=================================
ジョブ一覧を出力します。



Examples
=================================

基本的な使い方
--------------------------

``--job_type`` にジョブの種類を指定してください。指定できる値は以下の通りです。

* ``copy-project`` : プロジェクトのコピー
* ``gen-inputs`` : zipファイルから入力データの作成
* ``gen-tasks`` : タスクの作成
* ``gen-annotation`` : アノテーションZIPの更新
* ``gen-tasks-list`` : タスク全件ファイルの更新
* ``gen-inputs-list`` : 入力データ全件ファイルの更新
* ``delete-project`` : プロジェクトの削除
* ``invoke-hook`` : Webhookの起動
* ``move-project`` : プロジェクトの所属組織の移動



以下のコマンドは、プロジェクトprj1の「アノテーションzipの更新」のジョブ一覧を出力します。

.. code-block::

    $ annofabcli job list --project_id prj1 --job_type gen-annotation




出力結果
=================================

CSV出力
----------------------------------------------

.. code-block::

    $ annofabcli job list --project_id prj1 --job_type gen-annotation --format csv --output out.csv

`out.csv <https://github.com/kurusugawa-computer/annofab-cli/blob/master/docs/command_reference/job/list/out.csv>`_

JSON出力
----------------------------------------------

.. code-block::

    $ annofabcli job list --organization org1 --format pretty_json --output out.json



.. code-block::
    :caption: out.json

    [
        {
            "project_id": "prj1",
            "job_type": "gen-annotation",
            "job_id": "12345678-abcd-1234-abcd-1234abcd5678",
            "job_status": "succeeded",
            "job_execution": null,
            "job_detail": null,
            "created_datetime": "2020-12-23T03:02:56.478+09:00",
            "updated_datetime": "2020-12-23T03:02:56.478+09:00"
        },
        ...
    ]


