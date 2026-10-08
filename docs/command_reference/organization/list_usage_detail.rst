=============================================
organization list_usage_detail
=============================================

Description
=================================
指定した月の組織のエディタ利用状況明細をCSVまたはJSONで出力します。組織管理者として実行してください。

APIが提供するCSVの列名を標準化し、組織情報、ユーザー情報、プロジェクト名を付与します。
月別・日別の集計値を出力する場合は :doc:`list_usage` を使用してください。

Examples
=================================

.. code-block:: bash

    $ annofabcli organization list_usage_detail --organization org1 --month 2026-09 --output usage_detail.csv

年月の形式は :doc:`list_usage` と同じです。
``--format pretty_json`` を指定するとJSONで出力します。
``--output`` を省略すると標準出力に出力します。
出力先の親ディレクトリがない場合は作成します。取得・整形に失敗した場合は既存ファイルを保持します。

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
