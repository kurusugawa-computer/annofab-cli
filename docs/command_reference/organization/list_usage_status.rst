==================================
organization list_usage_status
==================================

Description
=================================
組織の月別または日別の利用状況を出力します。組織管理者として実行してください。

CSV・JSONともに、``--organization`` で指定した組織名を ``organization_name`` として出力します。

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

    $ annofabcli organization list_usage_status --organization org1 --month 2026-09 --output daily.csv

``--month`` を指定すると、その月の日別利用状況を出力します。
``--start_month``、``--end_month`` とは同時に指定できません。
日別CSVでは ``month`` の代わりに ``date`` が出力され、``created_datetime`` も追加されます。

出力結果
=================================

CSV出力
---------------------------------
ストレージ利用量を ``storage_usage_gb_hour`` （GB時）として出力します。
エディタ利用時間を ``image_editor_usage_hour``、``video_editor_usage_hour``、
``3d_editor_usage_hour`` の列に展開します。APIに含まれないエディタの利用時間は空欄です。
APIから追加のエディタ名が返された場合は、``{エディタ名}_usage_hour`` の列も出力します。
取得結果が0件でもヘッダ行を出力します。

.. csv-table:: out.csv
    :file: list_usage_status/out.csv
    :header-rows: 1

JSON出力
---------------------------------
JSONはCSVと同じ項目名・単位・レコード構造の配列として出力します。
APIに含まれないエディタの利用時間は、CSVでは空欄、JSONでは ``null`` になります。

.. code-block:: bash

    $ annofabcli organization list_usage_status --organization org1 --start_month 2026-09 --end_month 2026-09 --format pretty_json --output out.json

.. code-block:: json
    :caption: out.json

    [
        {
            "organization_id": "12345678-abcd-1234-abcd-1234abcd5678",
            "organization_name": "org1",
            "month": "2026-09",
            "aggregation_period_from": "2026-09-01T00:00:00+09:00",
            "aggregation_period_to": "2026-10-01T00:00:00+09:00",
            "storage_usage_gb_hour": 720.0,
            "image_editor_usage_hour": 12.5,
            "video_editor_usage_hour": 3.0,
            "3d_editor_usage_hour": null
        }
    ]

日別JSONでは ``month`` の代わりに ``date`` が含まれ、``created_datetime`` も含まれます。

Usage Details
=================================

.. argparse::
   :ref: annofabcli.organization.list_usage_status.add_parser
   :prog: annofabcli organization list_usage_status
   :nosubcommands:
   :nodefaultconst:
