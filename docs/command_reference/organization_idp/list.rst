==========================
organization_idp list
==========================

Description
=================================
組織IDプロバイダー一覧を出力します。クライアントシークレット（ ``client_secret`` ）は、すべての出力形式で除外します。

組織IDプロバイダーの利用を許可された組織で使用できます。取得には組織メンバーの権限が必要です。
詳細は `組織のIDプロバイダー一覧取得API <https://annofab.com/docs/api/#operation/getOrganizationIdpList>`_ を参照してください。

Examples
=================================

.. code-block::

    $ annofabcli organization_idp list --organization org1 --format csv --output out.csv

CSV形式では、 ``endpoints`` と ``attribute_mapping`` をドット区切りの列名に展開します。
IdPが未登録の場合、CSVはヘッダーのみ、JSONは空配列を出力します。

出力結果
=================================

CSV出力
----------------------------------------------

.. csv-table:: out.csv
    :file: list/out.csv
    :header-rows: 1

JSON出力
----------------------------------------------

.. code-block::

    $ annofabcli organization_idp list --organization org1 --format pretty_json --output out.json

.. code-block:: json
    :caption: out.json

    [
        {
            "organization_name": "org1",
            "id": "idp1",
            "client_id": "client1",
            "attributes_request_method": "GET",
            "endpoints": {
                "_type": "IssuerOnly",
                "issuer": "https://example.com"
            },
            "attribute_mapping": {
                "email": "email",
                "name": "name"
            },
            "sign_up_url": "https://example.com/signup",
            "created_datetime": "2026-10-05T12:00:00+09:00",
            "updated_datetime": "2026-10-05T12:00:00+09:00"
        }
    ]

Usage Details
=================================

.. argparse::
   :ref: annofabcli.organization_idp.list_organization_idp.add_parser
   :prog: annofabcli organization_idp list
   :nosubcommands:
   :nodefaultconst:
