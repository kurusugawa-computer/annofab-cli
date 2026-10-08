==================================
organization list_usage_status
==================================

Description
=================================
組織の月別または日別の利用状況を出力します。組織管理者として実行してください。

エディタ利用時間の単位は時間、ストレージ利用量の単位はGB時です。
作業時間や請求金額を出力するコマンドではありません。

Examples
=================================

月別利用状況
---------------------------------

.. code-block:: bash

    $ annofabcli organization list_usage_status --organization org1 --start_month 2026-08 --end_month 2026-09 --output out.csv

開始月と終了月はどちらも対象に含みます。年月は ``YYYY-MM`` 形式で指定します。
終了月を省略するとAPIはJSTでの現在の年月を使用します。
開始月を省略するとAPIは終了月の1年前を使用します。

日別利用状況
---------------------------------

.. code-block:: bash

    $ annofabcli organization list_usage_status --organization org1 --year_month 2026-09 --output daily.csv

``--year_month`` を指定すると、その月の日別利用状況を出力します。
``--start_month``、``--end_month`` とは同時に指定できません。
日別CSVでは ``year_month`` の代わりに ``date`` が出力され、``created_datetime`` も追加されます。

出力結果
=================================

CSV出力
---------------------------------
エディタ利用時間を ``editor_usage.image_editor``、``editor_usage.video_editor``、
``editor_usage.3d_editor`` の列に展開します。APIに含まれないエディタの利用時間は空欄です。
APIから追加のエディタ名が返された場合は、その列も出力します。
取得結果が0件でもヘッダ行を出力します。

.. csv-table:: out.csv
    :file: list_usage_status/out.csv
    :header-rows: 1

JSON出力
---------------------------------
JSONではAPIのレスポンスをそのまま出力します。

.. code-block:: bash

    $ annofabcli organization list_usage_status --organization org1 --start_month 2026-09 --end_month 2026-09 --format pretty_json --output out.json

.. code-block:: json
    :caption: out.json

    [
        {
            "organization_id": "12345678-abcd-1234-abcd-1234abcd5678",
            "year_month": "2026-09",
            "aggregation_period_from": "2026-09-01T00:00:00+09:00",
            "aggregation_period_to": "2026-10-01T00:00:00+09:00",
            "editor_usage": [
                {"editor_name": "image_editor", "value": 12.5},
                {"editor_name": "video_editor", "value": 3.0}
            ],
            "storage_usage": 720.0
        }
    ]

日別JSONでは ``year_month`` の代わりに ``date`` が含まれ、``created_datetime`` も含まれます。

Usage Details
=================================

.. argparse::
   :ref: annofabcli.organization.list_usage_status.add_parser
   :prog: annofabcli organization list_usage_status
   :nosubcommands:
   :nodefaultconst:
