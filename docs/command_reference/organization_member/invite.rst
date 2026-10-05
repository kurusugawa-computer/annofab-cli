==========================================
organization_member invite
==========================================

Description
=================================
組織にメンバーを招待します。


Examples
=================================


基本的な使い方
--------------------------

対象組織の名前を ``--organization`` に、招待するメンバーのuser_idを ``--user_id`` に、組織メンバーロールを ``--role`` に指定します。

``--organization`` に ``file://`` を先頭に付けたパスを指定すると、組織名の一覧が記載されたファイルを読み込めます。


.. code-block::

    $ annofabcli organization_member invite --organization org1 --user_id u1 u2 --role contributor

進捗と結果の出力については :ref:`organization_member_processing_logs` を参照してください。
すでに所属しているユーザと、確認に対して ``no`` と回答したユーザはスキップ件数に含まれます。



Usage Details
=================================

.. argparse::
   :ref: annofabcli.organization_member.invite_organization_member.add_parser
   :prog: annofabcli organization_member invite
   :nosubcommands:
   :nodefaultconst:
