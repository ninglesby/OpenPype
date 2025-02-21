from typing import List

import bpy

import pyblish.api
import openpype.api
import openpype.hosts.blender.api.action
from openpype.pipeline.publish import ValidateContentsOrder


class ValidateCameraZeroKeyframe(pyblish.api.InstancePlugin):
    """Camera must have a keyframe at frame 0.

    Unreal shifts the first keyframe to frame 0. Forcing the camera to have
    a keyframe at frame 0 will ensure that the animation will be the same
    in Unreal and Blender.
    """

    order = ValidateContentsOrder
    hosts = ["blender"]
    families = ["camera"]
    version = (0, 1, 0)
    label = "Zero Keyframe"
    actions = [openpype.hosts.blender.api.action.SelectInvalidAction]

    @staticmethod
    def get_invalid(instance) -> List:
        invalid = []
        for obj in instance:
            if isinstance(obj, bpy.types.Object) and obj.type == "CAMERA":
                if obj.animation_data and obj.animation_data.action:
                    action = obj.animation_data.action
                    frames_set = set()
                    for fcu in action.fcurves:
                        for kp in fcu.keyframe_points:
                            frames_set.add(kp.co[0])
                    frames = list(frames_set)
                    frames.sort()
                    if frames[0] != 0.0:
                        invalid.append(obj)
        return invalid

    def process(self, instance):
        invalid = self.get_invalid(instance)
        if invalid:
            raise RuntimeError(
                f"Camera must have a keyframe at frame 0: {invalid}"
            )
