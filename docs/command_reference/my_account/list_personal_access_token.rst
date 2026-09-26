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

CSV形式の場合、 ``note`` 、 ``id`` 、 ``permissions`` 、作成日時、最終利用日時、有効期限、 ``account_id`` の順に出力します。 ``permissions`` はJSON文字列として出力します。


出力結果
=================================

.. code-block::
   :caption: personal_access_tokens.csv

    note,id,permissions,created_datetime,last_used_datetime,expired_datetime,account_id
    GitHub Actions用,pat1,"[{""type"": ""all""}]",2026-01-01T00:00:00+09:00,2026-01-02T00:00:00+09:00,2026-12-31T00:00:00+09:00,account1


Usage Details
=================================

.. argparse::
   :ref: annofabcli.my_account.list_personal_access_token.add_parser
   :prog: annofabcli my_account list_personal_access_token
   :nosubcommands:
   :nodefaultconst:
