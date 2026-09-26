=====================================
my_account list_personal_access_token
=====================================

Description
=================================

自分が発行したパーソナルアクセストークンの一覧を出力します。トークン文字列そのものは出力されません。


Examples
=================================

CSV形式で出力する場合は、以下のように実行します。

.. code-block::

    $ annofabcli my_account list_personal_access_token --output personal_access_tokens.csv



出力結果
=================================

CSV出力
---------------------------------

.. csv-table:: personal_access_tokens.csv
   :header-rows: 1
   :file: list_personal_access_token/out.csv



JSON出力
---------------------------------

.. code-block::
   :caption: personal_access_tokens.json

    [
        {
            "id": "pat1",
            "account_id": "account1",
            "note": "GitHub Actions用",
            "expired_datetime": "2026-12-31T00:00:00+09:00",
            "permissions": [
                {
                    "type": "all"
                }
            ],
            "created_datetime": "2026-01-01T00:00:00+09:00",
            "last_used_datetime": "2026-01-02T00:00:00+09:00"
        }
    ]


Usage Details
=================================

.. argparse::
   :ref: annofabcli.my_account.list_personal_access_token.add_parser
   :prog: annofabcli my_account list_personal_access_token
   :nosubcommands:
   :nodefaultconst:
