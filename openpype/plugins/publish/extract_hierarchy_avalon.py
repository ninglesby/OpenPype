from copy import deepcopy
import pyblish.api
from openpype.client import (
    get_project,
    get_asset_by_id,
    get_asset_by_name,
    get_archived_assets
)
from openpype.pipeline import legacy_io


class ExtractHierarchyToAvalon(pyblish.api.ContextPlugin):
    """Create entities in Avalon based on collected data."""

    order = pyblish.api.ExtractorOrder - 0.01
    label = "Extract Hierarchy To Avalon"
    families = ["clip", "shot"]

    def process(self, context):
        # processing starts here
        if "hierarchyContext" not in context.data:
            self.log.info("skipping IntegrateHierarchyToAvalon")
            return

        if not legacy_io.Session:
            legacy_io.install()

        project_name = legacy_io.active_project()
        hierarchy_context = self._get_active_assets(context)
        self.log.debug("__ hierarchy_context: {}".format(hierarchy_context))

        self.project = None
        self.import_to_avalon(context, project_name, hierarchy_context)

    def import_to_avalon(
        self,
        context,
        project_name,
        input_data,
        parent=None,
    ):
        for name in input_data:
            self.log.info("input_data[name]: {}".format(input_data[name]))
            entity_data = input_data[name]
            entity_type = entity_data["entity_type"]

            data = {}
            data["entityType"] = entity_type

            # Custom attributes.
            for k, val in entity_data.get("custom_attributes", {}).items():
                data[k] = val

            if entity_type.lower() != "project":
                data["inputs"] = entity_data.get("inputs", [])

                # Tasks.
                tasks = entity_data.get("tasks", {})
                if tasks is not None or len(tasks) > 0:
                    data["tasks"] = tasks
                parents = []
                visualParent = None
                # do not store project"s id as visualParent
                if self.project is not None:
                    if self.project["_id"] != parent["_id"]:
                        visualParent = parent["_id"]
                        parents.extend(
                            parent.get("data", {}).get("parents", [])
                        )
                        parents.append(parent["name"])
                data["visualParent"] = visualParent
                data["parents"] = parents

            update_data = True
            # Process project
            if entity_type.lower() == "project":
                entity = get_project(project_name)
                # TODO: should be in validator?
                assert (entity is not None), "Did not find project in DB"

                # get data from already existing project
                cur_entity_data = entity.get("data") or {}
                cur_entity_data.update(data)
                data = cur_entity_data

                self.project = entity
            # Raise error if project or parent are not set
            elif self.project is None or parent is None:
                raise AssertionError(
                    "Collected items are not in right order!"
                )
            # Else process assset
            else:
                entity = get_asset_by_name(project_name, name)
                if entity:
                    # Do not override data, only update
                    cur_entity_data = entity.get("data") or {}
                    entity_tasks = cur_entity_data["tasks"] or {}

                    # create tasks as dict by default
                    if not entity_tasks:
                        cur_entity_data["tasks"] = entity_tasks

                    new_tasks = data.pop("tasks", {})
                    if "tasks" not in cur_entity_data and not new_tasks:
                        continue
                    for task_name in new_tasks:
                        if task_name in entity_tasks.keys():
                            continue
                        cur_entity_data["tasks"][task_name] = new_tasks[
                            task_name]
                    cur_entity_data.update(data)
                    data = cur_entity_data
                else:
                    # Skip updating data
                    update_data = False

                    archived_entities = get_archived_assets(
                        project_name,
                        asset_names=[name]
                    )
                    unarchive_entity = None
                    for archived_entity in archived_entities:
                        archived_parents = (
                            archived_entity
                            .get("data", {})
                            .get("parents")
                        )
                        if data["parents"] == archived_parents:
                            unarchive_entity = archived_entity
                            break

                    if unarchive_entity is None:
                        # Create entity if doesn"t exist
                        entity = self.create_avalon_asset(
                            name, data
                        )
                    else:
                        # Unarchive if entity was archived
                        entity = self.unarchive_entity(unarchive_entity, data)

                # make sure all relative instances have correct avalon data
                self._set_avalon_data_to_relative_instances(
                    context,
                    project_name,
                    entity
                )

            if update_data:
                # Update entity data with input data
                legacy_io.update_many(
                    {"_id": entity["_id"]},
                    {"$set": {"data": data}}
                )

            if "childs" in entity_data:
                self.import_to_avalon(
                    context, project_name, entity_data["childs"], entity
                )

    def unarchive_entity(self, entity, data):
        # Unarchived asset should not use same data
        new_entity = {
            "_id": entity["_id"],
            "schema": "openpype:asset-3.0",
            "name": entity["name"],
            "parent": self.project["_id"],
            "type": "asset",
            "data": data
        }
        legacy_io.replace_one(
            {"_id": entity["_id"]},
            new_entity
        )

        return new_entity

    def create_avalon_asset(self, name, data):
        asset_doc = {
            "schema": "openpype:asset-3.0",
            "name": name,
            "parent": self.project["_id"],
            "type": "asset",
            "data": data
        }
        self.log.debug("Creating asset: {}".format(asset_doc))
        asset_doc["_id"] = legacy_io.insert_one(asset_doc).inserted_id

        return asset_doc

    def _set_avalon_data_to_relative_instances(
        self,
        context,
        project_name,
        asset_doc
    ):
        for instance in context:
            # Skip instance if has filled asset entity
            if instance.data.get("assetEntity"):
                continue
            asset_name = asset_doc["name"]
            inst_asset_name = instance.data["asset"]

            if asset_name == inst_asset_name:
                instance.data["assetEntity"] = asset_doc

                # get parenting data
                parents = asset_doc["data"].get("parents") or list()

                # equire only relative parent
                parent_name = project_name
                if parents:
                    parent_name = parents[-1]

                # update avalon data on instance
                instance.data["anatomyData"].update({
                    "hierarchy": "/".join(parents),
                    "task": {},
                    "parent": parent_name
                })

    def _get_active_assets(self, context):
        """ Returns only asset dictionary.
            Usually the last part of deep dictionary which
            is not having any children
        """
        def get_pure_hierarchy_data(input_dict):
            input_dict_copy = deepcopy(input_dict)
            for key in input_dict.keys():
                self.log.debug("__ key: {}".format(key))
                # check if child key is available
                if input_dict[key].get("childs"):
                    # loop deeper
                    input_dict_copy[
                        key]["childs"] = get_pure_hierarchy_data(
                            input_dict[key]["childs"])
                elif key not in active_assets:
                    input_dict_copy.pop(key, None)
            return input_dict_copy

        hierarchy_context = context.data["hierarchyContext"]

        active_assets = []
        # filter only the active publishing insatnces
        for instance in context:
            if instance.data.get("publish") is False:
                continue

            if not instance.data.get("asset"):
                continue

            active_assets.append(instance.data["asset"])

        # remove duplicity in list
        active_assets = list(set(active_assets))
        self.log.debug("__ active_assets: {}".format(active_assets))

        return get_pure_hierarchy_data(hierarchy_context)
