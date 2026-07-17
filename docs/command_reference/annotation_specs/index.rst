==================================================
annotation_specs
==================================================

Description
=================================
アノテーション仕様関係のコマンドです。


Available Commands
=================================


.. toctree::
   :maxdepth: 1
   :titlesonly:

   add_attribute
   add_attribute_restriction
   add_attributes
   add_choices_to_attribute
   add_existing_attribute_to_labels
   add_label
   add_labels
   change_attribute_type
   delete_attribute_restriction
   diff
   export
   import
   list_attribute
   list_choice
   list_history
   list_inspection_phrase
   list_label
   list_label_attribute
   list_attribute_restriction
   list_label_color
   put_label_color
   set_attribute_required
   unset_attribute_required
   update_label_field_values


Usage Details
=================================

.. argparse::
   :ref: annofabcli.annotation_specs.subcommand_annotation_specs.add_parser
   :prog: annofabcli annotation_specs
   :nosubcommands:
