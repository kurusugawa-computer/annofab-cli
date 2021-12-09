==========================================
filesystem mask_user_info
==========================================

Description
=================================
CSVに記載されたユーザ情報をマスクします。CSVの以下の列をマスクします。

* user_id
* username
* biography
* account_id



Examples
=================================

基本的な使い方
--------------------------

``--csv`` にマスクしたいCSVファイルを指定してください。

.. code-block::

    $ annofabcli filesystem mask_user_info --csv user.csv


デフォルトでは1行ヘッダのCSVを読み込みます。複数行ヘッダのCSVを読み込む場合は、 ``--csv_header`` にヘッダの行数を指定してください。

.. code-block::

    $ annofabcli filesystem mask_user_info --csv user.csv --csv_header 2


``--not_masked_user_id`` には「マスクしないユーザ」のuser_idを指定できます。
以下のコマンドは、``alice`` 以外のユーザをマスクします。

.. code-block::

    $ annofabcli filesystem mask_user_info --csv user.csv --not_masked_user_id alice


``--not_masked_biography`` には「マスクしないbiographyであるユーザ」のuser_idを指定できます。
以下のコマンドはbiographyが ``Japan`` 以外のユーザをマスクします。


.. code-block::

    $ annofabcli filesystem mask_user_info --csv user.csv --not_masked_biography Japan




出力結果
=================================


.. csv-table:: user.csv
   :header: user_id,username,biography,task_count,account_id

    alice,Alice,Japan,1,alice
    bob,Bob,Japan,2,bob
    chris,Chris,China,3,Chris


.. code-block::

    $ annofabcli filesystem mask_user_info --csv user.csv --output out.csv


出力したファイルのuser_idは、"AA"のようにマスクされます。account_idとusernameはuser_idと同じ値です。biographyは"category-XX"のようにマスクされます。


.. csv-table:: user.csv
   :header: user_id,username,biography,task_count,account_id

    FF,FF,category-TD,1,FF
    AA,AA,category-TD,2,AA
    JE,JE,category-TU,3,JE

Usage Details
=================================

.. argparse::
   :ref: annofabcli.filesystem.mask_user_info.add_parser
   :prog: annofabcli filesystem mask_user_info
   :nosubcommands:
   :nodefaultconst:
