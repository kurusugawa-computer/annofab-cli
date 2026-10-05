==========================================
organization_member update_role
==========================================

Description
=================================
組織メンバのロールを更新します。





Examples
=================================


基本的な使い方
--------------------------

対象組織の名前を ``--organization`` に、変更対象のユーザのuser_idを ``--user_id`` に指定します。
設定するロールを ``--role`` に指定します。


.. code-block::

    $ annofabcli organization_member update_role --organization org1 --user_id u1 u2 --role contributor

進捗と結果の出力については :ref:`organization_member_processing_logs` を参照してください。
所属していないユーザと、確認に対して ``no`` と回答したユーザはスキップ件数に含まれます。


Usage Details
=================================

.. argparse::
   :ref: annofabcli.organization_member.update_organization_member_role.add_parser
   :prog: annofabcli organization_member update_role
   :nosubcommands:
   :nodefaultconst:
