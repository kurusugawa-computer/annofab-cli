=====================
job list_last
=====================

Description
=================================
複数プロジェクトに対して、最新のジョブを出力します。各プロジェクトの最新のジョブ状況を把握するのに利用できます。



Examples
=================================

基本的な使い方
--------------------------

``--job_type`` にジョブの種類を指定してください。
``--job_type`` に指定できる値は `Command line options <../../user_guide/command_line_options.html#job-type>`_ を参照してください。

プロジェクトを指定する場合は、``--project_id`` にproject_idを指定してください。

以下のコマンドは、プロジェクトprj1,prj2の「アノテーションzipの更新」の最新のジョブを出力します。

.. code-block::

    $ annofabcli job list_last --project_id prj1 prj2 --job_type gen-annotation


組織名を指定する場合は、``--organization`` を指定してください。自分自身が所属していて、進行中のプロジェクトが対象になります。

.. code-block::

    $ annofabcli job list_last --organization org1 --job_type gen-tasks-list



詳細な情報を出力する
-------------------------------------------------------
``--add_details`` を指定すると、プロジェクトの詳細な情報を出力します。具体的には以下の情報を出力します。

* ``task_last_updated_datetime`` : タスクの最終更新日時
* ``annotation_specs_last_updated_datetime`` : アノテーション仕様の最終更新日時

タスクやアノテーション仕様の更新日時に対して、アノテーションzipの更新日時（ ``gen-annotation`` の更新日時）が新しいかどうかを判断するのに利用できます。


出力結果
=================================

CSV出力
----------------------------------------------

.. code-block::

    $ annofabcli job list_last --project_id prj1 --job_type gen-annotation --format csv --output out.csv

`out.csv <https://github.com/kurusugawa-computer/annofab-cli/blob/main/docs/command_reference/job/list/out.csv>`_

JSON出力
----------------------------------------------

.. code-block::

    $ annofabcli job list --organization org1 --format pretty_json --output out.json



.. code-block::
    :caption: out.json

    [
        {
            "project_id": "prj1",
            "project_title": "prj_title1",
            "job_type": "gen-annotation",
            "job_id": "12345678-abcd-1234-abcd-1234abcd5678",
            "job_status": "succeeded",
            "job_execution": null,
            "job_detail": null,
            "created_datetime": "2021-01-05T03:02:51.722+09:00",
            "updated_datetime": "2021-01-05T03:02:51.722+09:00"
        },

        ...
    ]

Usage Details
=================================

.. argparse::
   :ref: annofabcli.job.list_last_job.add_parser
   :prog: annofabcli job list_last
   :nosubcommands:
   :nodefaultconst:
