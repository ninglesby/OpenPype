from .api.utils import (
    setup,
    get_resolve_module
)

from .api.pipeline import (
    install,
    uninstall,
    ls,
    containerise,
    publish,
    launch_workfiles_app,
    maintained_selection
)

from .api.lib import (
    publish_clip_color,
    get_project_manager,
    get_current_project,
    get_current_sequence,
    create_bin,
    get_video_track_names,
    get_current_track_items,
    get_track_item_pype_tag,
    set_track_item_pype_tag,
    imprint,
    set_publish_attribute,
    get_publish_attribute,
    create_compound_clip,
    swap_clips,
    get_pype_clip_metadata,
    set_project_manager_to_folder_name,
    get_reformated_path,
    get_otio_clip_instance_data
)

from .api.menu import launch_pype_menu

from .api.plugin import (
    SequenceLoader,
    Creator,
    PublishClip
)

from .api.workio import (
    open_file,
    save_file,
    current_file,
    has_unsaved_changes,
    file_extensions,
    work_root
)

bmdvr = None
bmdvf = None

__all__ = [
    # pipeline
    "install",
    "uninstall",
    "ls",
    "containerise",
    "reload_pipeline",
    "publish",
    "launch_workfiles_app",
    "maintained_selection",

    # utils
    "setup",
    "get_resolve_module",

    # lib
    "publish_clip_color",
    "get_project_manager",
    "get_current_project",
    "get_current_sequence",
    "create_bin",
    "get_video_track_names",
    "get_current_track_items",
    "get_track_item_pype_tag",
    "set_track_item_pype_tag",
    "imprint",
    "set_publish_attribute",
    "get_publish_attribute",
    "create_compound_clip",
    "swap_clips",
    "get_pype_clip_metadata",
    "set_project_manager_to_folder_name",
    "get_reformated_path",
    "get_otio_clip_instance_data",

    # menu
    "launch_pype_menu",

    # plugin
    "SequenceLoader",
    "Creator",
    "PublishClip",

    # workio
    "open_file",
    "save_file",
    "current_file",
    "has_unsaved_changes",
    "file_extensions",
    "work_root",

    # singleton with black magic resolve module
    "bmdvr",
    "bmdvf"
]
