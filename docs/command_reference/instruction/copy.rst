=================================
instruction copy
=================================

Description
=================================
作業ガイドを別のプロジェクトにコピーします。



Examples
=================================

基本的な使い方
--------------------------


以下のコマンドは、プロジェクトprj1の作業ガイドをプロジェクトprj2にコピーします。

.. code-block::

    $ annofabcli instruction copy prj1 prj2

Usage Details
=================================

.. argparse::
   :ref: annofabcli.instruction.copy_instruction.add_parser
   :prog: annofabcli instruction copy
   :nosubcommands:
   :nodefaultconst:
