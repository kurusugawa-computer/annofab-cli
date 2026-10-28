==========================================
organization_member delete
==========================================

Description
=================================
組織からメンバーを脱退させます。


Examples
=================================


基本的な使い方
--------------------------

対象組織の名前を ``--organization`` に、脱退させるメンバーのuser_idを ``--user_id`` に指定します。


.. code-block::

    $ annofabcli organization_member delete --organization org1 --user_id u1 u2 

進捗と結果の出力については :ref:`organization_member_processing_logs` を参照してください。
所属していないユーザと、確認に対して ``no`` と回答したユーザはスキップ件数に含まれます。


Usage Details
=================================

.. argparse::
   :ref: annofabcli.organization_member.delete_organization_member.create_parser
   :prog: annofabcli organization_member delete
   :nosubcommands:
   :nodefaultconst:
