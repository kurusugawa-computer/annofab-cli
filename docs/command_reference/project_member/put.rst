=================================
project_member put
=================================

Description
=================================
プロジェクトメンバを登録します。



Examples
=================================

基本的な使い方
--------------------------
``--csv`` に、プロジェクトメンバ情報が記載されているCSVファイルを指定してください。
CSVファイルのフォーマットは以下の通りです。

* カンマ区切り
* ヘッダ行あり

  * ``user_id`` : 登録対象のユーザーID
  * ``member_role`` : メンバーのロール。指定できる値は以下を参照してください。
  * ``sampling_inspection_rate`` ：抜取検査率
  * ``sampling_acceptance_rate`` ：抜取受入率
            

``member_role`` に指定できる値は以下の通りです。

* ``worker`` : アノテータ
* ``accepter`` : チェッカー
* ``training_data_user`` : アノテーションユーザ
* ``owner`` : プロジェクトオーナ


以下は、CSVファイルのサンプルです。

.. code-block::
    :caption: member.csv

    user_id,member_role,sampling_inspection_rate,sampling_acceptance_rate
    user1,worker,,
    user2,accepter,80,40


.. code-block::

    $ annofabcli project_member put --project_id prj1 --csv members.csv


CSVに記載されていないメンバを削除する場合は、 ``--delete`` を指定してください。

.. code-block::

    $ annofabcli project_member put --project_id prj1 --csv members.csv --delete

Usage Details
=================================

.. argparse::
   :ref: annofabcli.project_member.put_project_members.add_parser
   :prog: annofabcli project_member put
   :nosubcommands:
   :nodefaultconst:
