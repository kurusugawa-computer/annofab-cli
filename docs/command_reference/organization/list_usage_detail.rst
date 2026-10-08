=============================================
organization list_usage_detail
=============================================

Description
=================================
指定した期間の組織のエディタ利用状況明細をCSVまたはJSONで出力します。組織管理者として実行してください。
期間を省略すると日本時間（JST）の現在の月のみ取得します。

APIが提供するCSVの列名を標準化し、組織情報、ユーザー情報、プロジェクト名を付与します。
月別・日別の集計値を出力する場合は :doc:`list_usage` を使用してください。

Examples
=================================

.. code-block:: bash

    $ annofabcli organization list_usage_detail --organization org1 --start_month 2026-07 --end_month 2026-09 --output usage_detail.csv

年月の形式は :doc:`list_usage` と同じです。
開始月と終了月を含む各月の明細を取得し、1つのCSVまたはJSONに結合します。
``--end_month`` の省略時は日本時間の現在の月、``--start_month`` の省略時は終了月と同じ月になります。
単月を取得する場合は、``--end_month 2026-09`` のように終了月だけ指定できます。
開始月だけ指定すると、その月から現在の月までを取得します。
開始月が終了月より後の場合はエラーになります。

``--format pretty_json`` を指定するとJSONで出力します。
``--output`` を省略すると標準出力に出力します。
出力先の親ディレクトリがない場合は作成します。すべての月の取得・整形が成功してから出力します。
途中の月で取得に失敗した場合も、既存ファイルを保持します。

出力結果
=================================
CSVとJSONは同じ項目を出力します。

.. csv-table:: CSV出力例
   :file: list_usage_detail/out.csv
   :header-rows: 1

.. code-block:: json

    [
      {
        "organization_id": "org-id",
        "organization_name": "org1",
        "date": "2026-09-01",
        "editor_name": "image_editor",
        "project_id": "project-id",
        "project_title": "プロジェクトA",
        "account_id": "account-id",
        "user_id": "alice",
        "username": "利用者A",
        "editor_usage_hour": 1.5
      }
    ]

出力項目の説明
---------------------------------

.. list-table::
   :header-rows: 1

   * - 項目
     - 説明
   * - organization_id / organization_name
     - 組織ID / 組織名
   * - date
     - 利用日（APIの ``date``）
   * - editor_name
     - エディタ名（APIの ``editorName``）
   * - project_id
     - プロジェクトID（APIの ``projectId``）
   * - project_title
     - 現在のプロジェクト名
   * - account_id
     - アカウントID（APIの ``accountId``）
   * - user_id / username
     - 現在の組織メンバー情報から補完したユーザーID / ユーザー名
   * - editor_usage_hour
     - エディタ利用時間。単位は時間（APIの ``editorUsageTime``）

プロジェクト名・ユーザー情報は現在の情報であり、利用当時の情報とは異なる場合があります。
削除済みのプロジェクトや組織から脱退したユーザーなど、対応する情報が見つからない場合も明細は残します。
補完できない項目はCSVでは空欄、JSONでは ``null`` です。

明細にストレージ利用量は含まれません。
明細が0件の場合は、CSVではヘッダ行のみ、JSONでは空配列を出力します。

Usage Details
=================================

.. argparse::
   :ref: annofabcli.organization.list_usage_detail.add_parser
   :prog: annofabcli organization list_usage_detail
   :nosubcommands:
   :nodefaultconst:
