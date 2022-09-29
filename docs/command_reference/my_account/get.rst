=====================
my_account get
=====================

Description
=================================
自分のアカウント情報を出力します。



Examples
=================================

.. code-block::

    $ annofabcli my_account get
    {
        "account_id": "12345678-abcd-1234-abcd-1234abcd5678",
        "user_id": "alice",
        "username": "Alice",
        "email": "alice@example.com",
        "reset_requested_email": null,
        "lang": "ja-JP",
        "keylayout": "ja-JP",
        "authority": "user",
        "biography": "U.K.",
        "errors": [],
        "updated_datetime": "2022-07-01T00:01:09.801+09:00",
        "account_type": "annofab"
    }





Usage Details
=================================

.. argparse::
   :ref: annofabcli.my_account.get_my_account.add_parser
   :prog: annofabcli my_account get
   :nosubcommands:
   :nodefaultconst:

