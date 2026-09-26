=======================================
my_account revoke_personal_access_token
=======================================

Description
=================================

自分が発行したパーソナルアクセストークンを無効化します。無効化後、そのトークンではAnnofab APIにアクセスできません。


Examples
=================================

パーソナルアクセストークンのIDを指定して実行します。IDは :doc:`list_personal_access_token` で確認できます。

.. code-block::

    $ annofabcli my_account revoke_personal_access_token --personal_access_token_id pat1


Usage Details
=================================

.. argparse::
   :ref: annofabcli.my_account.revoke_personal_access_token.add_parser
   :prog: annofabcli my_account revoke_personal_access_token
   :nosubcommands:
   :nodefaultconst:
