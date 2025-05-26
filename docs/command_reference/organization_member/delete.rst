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


Usage Details
=================================

.. argparse::
   :ref: annofabcli.organization_member.delete_organization_member.add_parser
   :prog: annofabcli organization_member delete
   :nosubcommands:
   :nodefaultconst:
