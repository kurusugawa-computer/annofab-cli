=====================
webhook list
=====================

Description
=================================
Webhook一覧を出力します。


Examples
=================================

基本的な使い方
--------------------------

以下のコマンドは、プロジェクトprj1のWebhook一覧をCSV形式で出力します。

.. code-block::

    $ annofabcli webhook list --project_id prj1 --format csv --output out.csv

CSV形式の場合、 ``headers`` はJSON文字列として出力します。 ``body`` は文字列としてそのまま出力します。


出力結果
=================================

CSV出力
----------------------------------------------

.. code-block::

    $ annofabcli webhook list --project_id prj1 --format csv --output out.csv

JSON出力
----------------------------------------------

.. code-block::

    $ annofabcli webhook list --project_id prj1 --format pretty_json --output out.json


.. code-block::
    :caption: out.json

    [
        {
            "project_id": "prj1",
            "webhook_id": "webhook1",
            "webhook_status": "active",
            "event_type": "task-completed",
            "method": "POST",
            "url": "https://example.com/webhook",
            "headers": [
                {
                    "name": "Content-Type",
                    "value": "application/json"
                }
            ],
            "body": "{\"project_id\":\"{{PROJECT_ID}}\",\"task_id\":\"{{TASK_ID}}\"}",
            "created_datetime": "2026-01-23T03:02:56.478+09:00",
            "updated_datetime": "2026-01-23T03:02:56.478+09:00"
        },
        ...
    ]

Usage Details
=================================

.. argparse::
   :ref: annofabcli.webhook.list_webhook.add_parser
   :prog: annofabcli webhook list
   :nosubcommands:
   :nodefaultconst:
