import pyblish.api
import colorbleed.api


class ValidateIntermediateDirectoriesChecked(pyblish.api.InstancePlugin):
    """Validate Create Intermediate Directories is enabled on ROP node."""

    order = colorbleed.api.ValidateContentsOrder
    families = ['colorbleed.pointcache',
                'colorbleed.camera']
    hosts = ['houdini']
    label = 'Create Intermediate Directories Checked'

    def process(self, instance):

        invalid = self.get_invalid(instance)
        if invalid:
            raise RuntimeError("Found ROP nodes with Create Intermediate "
                               "Directories turned off")

    @classmethod
    def get_invalid(cls, instance):

        result = []

        for node in instance[:]:
            if node.parm("mkpath").eval() != 1:
                cls.log.error("Invalid settings found on `%s`" % node.path())
                result.append(node.path())

        return result


