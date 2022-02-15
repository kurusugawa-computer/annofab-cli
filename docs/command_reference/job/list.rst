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

``--job_type`` にジョブの種類を指定してください。``--job_type`` に指定できる値は `Command line options <../../user_guide/command_line_options.html#job-type>`_ を参照してください。



以下のコマンドは、プロジェクトprj1の「アノテーションzipの更新」のジョブ一覧を出力します。

.. code-block::

    $ annofabcli job list --project_id prj1 --job_type gen-annotation




出力結果
=================================

CSV出力
----------------------------------------------

.. code-block::

    $ annofabcli job list --project_id prj1 --job_type gen-annotation --format csv --output out.csv

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

Usage Details
=================================

.. argparse::
   :ref: annofabcli.job.list_job.add_parser
   :prog: annofabcli job list
   :nosubcommands:
   :nodefaultconst:
