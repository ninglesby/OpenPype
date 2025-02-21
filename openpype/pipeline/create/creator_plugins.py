import os
import copy

from abc import (
    ABCMeta,
    abstractmethod,
    abstractproperty
)
import six

from openpype.settings import get_system_settings, get_project_settings
from .subset_name import get_subset_name
from openpype.pipeline.plugin_discover import (
    discover,
    register_plugin,
    register_plugin_path,
    deregister_plugin,
    deregister_plugin_path
)

from .legacy_create import LegacyCreator


class CreatorError(Exception):
    """Should be raised when creator failed because of known issue.

    Message of error should be user readable.
    """

    def __init__(self, message):
        super(CreatorError, self).__init__(message)


@six.add_metaclass(ABCMeta)
class BaseCreator:
    """Plugin that create and modify instance data before publishing process.

    We should maybe find better name as creation is only one part of it's logic
    and to avoid expectations that it is the same as `avalon.api.Creator`.

    Single object should be used for multiple instances instead of single
    instance per one creator object. Do not store temp data or mid-process data
    to `self` if it's not Plugin specific.
    """

    # Label shown in UI
    label = None
    group_label = None
    # Cached group label after first call 'get_group_label'
    _cached_group_label = None

    # Variable to store logger
    _log = None

    # Creator is enabled (Probably does not have reason of existence?)
    enabled = True

    # Creator (and family) icon
    # - may not be used if `get_icon` is reimplemented
    icon = None

    # Instance attribute definitions that can be changed per instance
    # - returns list of attribute definitions from
    #       `openpype.pipeline.attribute_definitions`
    instance_attr_defs = []

    # Filtering by host name - can be used to be filtered by host name
    # - used on all hosts when set to 'None' for Backwards compatibility
    #   - was added afterwards
    # QUESTION make this required?
    host_name = None

    def __init__(
        self, project_settings, system_settings, create_context, headless=False
    ):
        # Reference to CreateContext
        self.create_context = create_context
        self.project_settings = project_settings

        # Creator is running in headless mode (without UI elemets)
        # - we may use UI inside processing this attribute should be checked
        self.headless = headless

    @property
    def identifier(self):
        """Identifier of creator (must be unique).

        Default implementation returns plugin's family.
        """

        return self.family

    @abstractproperty
    def family(self):
        """Family that plugin represents."""

        pass

    @property
    def project_name(self):
        """Family that plugin represents."""

        return self.create_context.project_name

    @property
    def host(self):
        return self.create_context.host

    def get_group_label(self):
        """Group label under which are instances grouped in UI.

        Default implementation use attributes in this order:
            - 'group_label' -> 'label' -> 'identifier'
                Keep in mind that 'identifier' use 'family' by default.

        Returns:
            str: Group label that can be used for grouping of instances in UI.
                Group label can be overriden by instance itself.
        """

        if self._cached_group_label is None:
            label = self.identifier
            if self.group_label:
                label = self.group_label
            elif self.label:
                label = self.label
            self._cached_group_label = label
        return self._cached_group_label

    @property
    def log(self):
        """Logger of the plugin.

        Returns:
            logging.Logger: Logger with name of the plugin.
        """

        if self._log is None:
            from openpype.api import Logger

            self._log = Logger.get_logger(self.__class__.__name__)
        return self._log

    def _add_instance_to_context(self, instance):
        """Helper method to add instance to create context.

        Instances should be stored to DCC workfile metadata to be able reload
        them and also stored to CreateContext in which is creator plugin
        existing at the moment to be able use it without refresh of
        CreateContext.

        Args:
            instance (CreatedInstance): New created instance.
        """

        self.create_context.creator_adds_instance(instance)

    def _remove_instance_from_context(self, instance):
        """Helper method to remove instance from create context.

        Instances must be removed from DCC workfile metadat aand from create
        context in which plugin is existing at the moment of removement to
        propagate the change without restarting create context.

        Args:
            instance (CreatedInstance): Instance which should be removed.
        """

        self.create_context.creator_removed_instance(instance)

    @abstractmethod
    def create(self):
        """Create new instance.

        Replacement of `process` method from avalon implementation.
        - must expect all data that were passed to init in previous
            implementation
        """

        pass

    @abstractmethod
    def collect_instances(self):
        """Collect existing instances related to this creator plugin.

        The implementation differs on host abilities. The creator has to
        collect metadata about instance and create 'CreatedInstance' object
        which should be added to 'CreateContext'.

        Example:
        ```python
        def collect_instances(self):
            # Getting existing instances is different per host implementation
            for instance_data in pipeline.list_instances():
                # Process only instances that were created by this creator
                creator_id = instance_data.get("creator_identifier")
                if creator_id == self.identifier:
                    # Create instance object from existing data
                    instance = CreatedInstance.from_existing(
                        instance_data, self
                    )
                    # Add instance to create context
                    self._add_instance_to_context(instance)
        ```
        """

        pass

    @abstractmethod
    def update_instances(self, update_list):
        """Store changes of existing instances so they can be recollected.

        Args:
            update_list(List[UpdateData]): Gets list of tuples. Each item
                contain changed instance and it's changes.
        """

        pass

    @abstractmethod
    def remove_instances(self, instances):
        """Method called on instance removement.

        Can also remove instance metadata from context but should return
        'True' if did so.

        Args:
            instance(List[CreatedInstance]): Instance objects which should be
                removed.
        """

        pass

    def get_icon(self):
        """Icon of creator (family).

        Can return path to image file or awesome icon name.
        """

        return self.icon

    def get_dynamic_data(
        self, variant, task_name, asset_doc, project_name, host_name
    ):
        """Dynamic data for subset name filling.

        These may be get dynamically created based on current context of
        workfile.
        """

        return {}

    def get_subset_name(
        self, variant, task_name, asset_doc, project_name, host_name=None
    ):
        """Return subset name for passed context.

        CHANGES:
        Argument `asset_id` was replaced with `asset_doc`. It is easier to
        query asset before. In some cases would this method be called multiple
        times and it would be too slow to query asset document on each
        callback.

        NOTE:
        Asset document is not used yet but is required if would like to use
        task type in subset templates.

        Args:
            variant(str): Subset name variant. In most of cases user input.
            task_name(str): For which task subset is created.
            asset_doc(dict): Asset document for which subset is created.
            project_name(str): Project name.
            host_name(str): Which host creates subset.
        """

        dynamic_data = self.get_dynamic_data(
            variant, task_name, asset_doc, project_name, host_name
        )

        return get_subset_name(
            self.family,
            variant,
            task_name,
            asset_doc,
            project_name,
            host_name,
            dynamic_data=dynamic_data,
            project_settings=self.project_settings
        )

    def get_instance_attr_defs(self):
        """Plugin attribute definitions.

        Attribute definitions of plugin that hold data about created instance
        and values are stored to metadata for future usage and for publishing
        purposes.

        NOTE:
        Convert method should be implemented which should care about updating
        keys/values when plugin attributes change.

        Returns:
            List[AbtractAttrDef]: Attribute definitions that can be tweaked for
                created instance.
        """

        return self.instance_attr_defs


class Creator(BaseCreator):
    """Creator that has more information for artist to show in UI.

    Creation requires prepared subset name and instance data.
    """

    # GUI Purposes
    # - default_variants may not be used if `get_default_variants` is overriden
    default_variants = []

    # Default variant used in 'get_default_variant'
    default_variant = None

    # Short description of family
    # - may not be used if `get_description` is overriden
    description = None

    # Detailed description of family for artists
    # - may not be used if `get_detail_description` is overriden
    detailed_description = None

    # It does make sense to change context on creation
    # - in some cases it may confuse artists because it would not be used
    #      e.g. for buld creators
    create_allow_context_change = True

    # Precreate attribute definitions showed before creation
    # - similar to instance attribute definitions
    pre_create_attr_defs = []

    @abstractmethod
    def create(self, subset_name, instance_data, pre_create_data):
        """Create new instance and store it.

        Ideally should be stored to workfile using host implementation.

        Args:
            subset_name(str): Subset name of created instance.
            instance_data(dict): Base data for instance.
            pre_create_data(dict): Data based on pre creation attributes.
                Those may affect how creator works.
        """

        # instance = CreatedInstance(
        #     self.family, subset_name, instance_data
        # )
        pass

    def get_description(self):
        """Short description of family and plugin.

        Returns:
            str: Short description of family.
        """

        return self.description

    def get_detail_description(self):
        """Description of family and plugin.

        Can be detailed with markdown or html tags.

        Returns:
            str: Detailed description of family for artist.
        """

        return self.detailed_description

    def get_default_variants(self):
        """Default variant values for UI tooltips.

        Replacement of `defatults` attribute. Using method gives ability to
        have some "logic" other than attribute values.

        By default returns `default_variants` value.

        Returns:
            List[str]: Whisper variants for user input.
        """

        return copy.deepcopy(self.default_variants)

    def get_default_variant(self):
        """Default variant value that will be used to prefill variant input.

        This is for user input and value may not be content of result from
        `get_default_variants`.

        Can return `None`. In that case first element from
        `get_default_variants` should be used.
        """

        return self.default_variant

    def get_pre_create_attr_defs(self):
        """Plugin attribute definitions needed for creation.
        Attribute definitions of plugin that define how creation will work.
        Values of these definitions are passed to `create` method.

        Note:
            Convert method should be implemented which should care about
            updating keys/values when plugin attributes change.

        Returns:
            List[AbtractAttrDef]: Attribute definitions that can be tweaked for
                created instance.
        """
        return self.pre_create_attr_defs


class HiddenCreator(BaseCreator):
    @abstractmethod
    def create(self, instance_data, source_data):
        pass


class AutoCreator(BaseCreator):
    """Creator which is automatically triggered without user interaction.

    Can be used e.g. for `workfile`.
    """

    def remove_instances(self, instances):
        """Skip removement."""
        pass


def discover_creator_plugins():
    return discover(BaseCreator)


def discover_legacy_creator_plugins():
    from openpype.lib import Logger

    log = Logger.get_logger("CreatorDiscover")

    plugins = discover(LegacyCreator)
    project_name = os.environ.get("AVALON_PROJECT")
    system_settings = get_system_settings()
    project_settings = get_project_settings(project_name)
    for plugin in plugins:
        try:
            plugin.apply_settings(project_settings, system_settings)
        except Exception:
            log.warning(
                "Failed to apply settings to loader {}".format(
                    plugin.__name__
                ),
                exc_info=True
            )
    return plugins


def get_legacy_creator_by_name(creator_name, case_sensitive=False):
    """Find creator plugin by name.

    Args:
        creator_name (str): Name of creator class that should be returned.
        case_sensitive (bool): Match of creator plugin name is case sensitive.
            Set to `False` by default.

    Returns:
        Creator: Return first matching plugin or `None`.
    """

    # Lower input creator name if is not case sensitive
    if not case_sensitive:
        creator_name = creator_name.lower()

    for creator_plugin in discover_legacy_creator_plugins():
        _creator_name = creator_plugin.__name__

        # Lower creator plugin name if is not case sensitive
        if not case_sensitive:
            _creator_name = _creator_name.lower()

        if _creator_name == creator_name:
            return creator_plugin
    return None


def register_creator_plugin(plugin):
    if issubclass(plugin, BaseCreator):
        register_plugin(BaseCreator, plugin)

    elif issubclass(plugin, LegacyCreator):
        register_plugin(LegacyCreator, plugin)


def deregister_creator_plugin(plugin):
    if issubclass(plugin, BaseCreator):
        deregister_plugin(BaseCreator, plugin)

    elif issubclass(plugin, LegacyCreator):
        deregister_plugin(LegacyCreator, plugin)


def register_creator_plugin_path(path):
    register_plugin_path(BaseCreator, path)
    register_plugin_path(LegacyCreator, path)


def deregister_creator_plugin_path(path):
    deregister_plugin_path(BaseCreator, path)
    deregister_plugin_path(LegacyCreator, path)
