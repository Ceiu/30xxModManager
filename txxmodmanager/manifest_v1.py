#!/usr/bin/env python3

# Classes for processing manifests following the v1 spec

import lib.yaml as yaml
import logging
import os
import shutil

from enum import Enum
from txxmodmanager import util as mm_util
from txxmodmanager.filesystem import FileSystem


# This is assumed to be setup before the package is imported; otherwise we get ugly defaults
log = logging.getLogger('TxxModManager')



class Change():
    class State(Enum):
        UNKNOWN = 0
        STAGED = 1
        OVERWRITTEN = 2

    def __init__(self, state = State.STAGED):
        self.state = state

    def apply(self):
        raise NotImplementedError("not yet implemented")



class ChangeMap():
    def __init__(self):
        # list of changes in order received (logging)
        self._changes = []

        # mapping of files to list of active changes (applying)
        self._filemap = {}

    def apply(self):
        for change in self._changes:
            if change.state == Change.State.STAGED:
                change.apply()




class TaskFactory():
    TYPE_KEY="type"

    def __init__(self, define_builtin=True):
        self.__taskmap = {}

        if define_builtin:
            self.define_builtin_tasks()

    def define_builtin_tasks(self):
        self.define_task('file', FileTask)
        self.define_task('sprite', SpriteTask)

    def define_task(self, task_type, task_class):
        if not isinstance(task_type, str) or len(task_type) == 0:
            raise ValueError("type name must be a non-empty string")

        if not isinstance(task_class, type) or not issubclass(task_class, Task):
            raise TypeError("task_class must be a type derived from the Task class")

        self.__taskmap[task_type] = task_class

    def remove_task(self, task_type):
        del self__taskmap[task_type]

    def build(self, task_type):
        # TODO: This needs to fail nicer so we can capture all errors in a given manifest at once
        # for usability to not suck. Fine for a prototype, no bueno for a proper release.

        task_class = self.__taskmap.get(task_type)
        if task_class is None:
            raise ValueError(f"no such task type defined: {task_type}")

        return task_class()

    def build_from_node(self, task_node):
        # TODO: This needs to fail nicer so we can capture all errors in a given manifest at once
        # for usability to not suck. Fine for a prototype, no bueno for a proper release.

        if not isinstance(task_node, dict):
            raise TypeError("task node is not a dictionary")

        if not TaskFactory.TYPE_KEY in task_node:
            raise ValueError("task node lacks a type field")

        task = self.build(task_node[TaskFactory.TYPE_KEY])
        task.populate(task_node)

        return task







class Context():

    def __init__(self, source_filesystem, target_filesystem):
        if not isinstance(source_filesystem, FileSystem):
            raise TypeError("source_filesystem must be a type derived from the FileSystem class")

        if not isinstance(target_filesystem, FileSystem):
            raise TypeError("target_filesystem must be a type derived from the FileSystem class")

        self.__source_filesystem = source_filesystem
        self.__target_filesystem = target_filesystem
        self.__errors = []
        self.__warnings = []

    @property
    def source_filesystem(self):
        return self.__source_filesystem

    @property
    def target_filesystem(self):
        return self.__target_filesystem

    @property
    def errors(self):
        return tuple(self.__errors)

    def add_error(self, msg):
        self.__errors.append(msg)

    @property
    def warnings(self):
        return tuple(self.__warnings)

    def add_warning(self, msg):
        self.__warnings.append(msg)




# manifest:
#   the main manifest.yml file; contains the basic information about the mod and the task list
#   to execute
#
# task list:
#   a collection of tasks to perform; eventually permit including task lists for handy reuse
#
# task:
#   an individual task to be performed by the mod manager; delegated to a task handler



class ManifestNode():
    NAME_KEY="name"
    DESC_KEY="desc"

    MAX_NAME_LENGTH=64
    MAX_DESC_LENGTH=1024

    def __init__(self):
        self.reset()

    def __str__(self):
        return f"{self.__class__.__name__} [name: {self.name}, desc: {str(self.desc)[:32]}]"

    def reset(self):
        self.__name = None
        self.__desc = None

    @property
    def name(self):
        return self.__name

    @property
    def desc(self):
        return self.__desc

    def populate(self, source):
        if not isinstance(source, dict):
            raise TypeError("attempting to populate node from non-dict source")

        self.reset()

        if ManifestNode.NAME_KEY in source:
            self.__name = mm_util.normalize_str(source[ManifestNode.NAME_KEY], ManifestNode.MAX_NAME_LENGTH)

        if ManifestNode.DESC_KEY in source:
            self.__desc = mm_util.normalize_str(source[ManifestNode.DESC_KEY], ManifestNode.MAX_DESC_LENGTH)

    def export(self):
        return {
            Task.NAME_KEY: self.name,
            Task.DESC_KEY: self.desc
        }

    def list_resources(self):
        return []

    def validate(self, context):
        if not isinstance(context, Context):
            raise TypeError("context must be a type derived from the Context class")

        # TODO: Add any general validation checks here
        return True

    def apply(self, context):
        if not isinstance(context, Context):
            raise TypeError("context must be a type derived from the Context class")

        # TODO: Add any general application tasks here
        return True





class Task(ManifestNode):
    TYPE_KEY="type"
    TAGS_KEY="tags"

    MAX_TAG_LENGTH=255

    def __init__(self, type):
        if not isinstance(type, str) or len(type) == 0:
            raise ValueError("type must be a non-empty string")

        self.__type = type

        super().__init__()

    def __str__(self):
        return f"{self.__class__.__name__} [type: {self.type}, name: {self.name}, tags: {self.tags}]"

    def reset(self):
        super().reset()

        self.__tags = set()

    @property
    def type(self):
        return self.__type

    @property
    def tags(self):
        return list(self.__tags)

    def add_tag(self, tag):
        if not isinstance(tag, str):
            raise TypeError(f"tags must be of type string; received: {type(tag)}")

        if len(tag) > Task.MAX_TAG_LENGTH:
            raise ValueError(f"tag is longer tha maximum allowed length: {len(tag)} > {Task.MAX_TAG_LENGTH}")

        self.__tags.add(tag.strip())

    def populate(self, source):
        super().populate(source)

        # TODO: Is this even necessary? Possibly overkill
        if not Task.TYPE_KEY in source or source[Task.TYPE_KEY] != self.type:
            raise ValueError(f"populate source type mismatch: {source[Task.TYPE_KEY]} != {self.type}")

        if Task.TAGS_KEY in source:
            tags = source[Task.TAGS_KEY]

            if isinstance(tags, str):
                self.add_tag(mm_util.normalize_str(tags, Task.MAX_TAG_LENGTH))

            if isinstance(tags, list) or isinstance(tags, tuple):
                for tag in tags:
                    self.add_tag(mm_util.normalize_str(tag, Task.MAX_TAG_LENGTH))

    def export(self):
        node = super().export()

        node[Task.TAGS_KEY] = self.tags
        node[Task.TYPE_KEY] = self.type

        return node

    def validate(self, context):
        result = super().validate(context)

        # TODO: Add any general validation checks here
        return result

    def apply(self, context):
        result = super().apply(context)

        # TODO: Add any general application tasks here
        return result


class FileTask(Task):
    SOURCE_KEY="source"
    TARGET_KEY="target"
    REQUIRE_TARGET_KEY="require_target"

    def __init__(self):
        super().__init__("file")

    def reset(self):
        super().reset()

        self.__source = None
        self.__target = None
        self.__require_target = True

    @property
    def source(self):
        return self.__source

    @property
    def target(self):
        return self.__target

    @property
    def require_target(self):
        return self.__require_target

    def populate(self, source):
        super().populate(source)

        if FileTask.SOURCE_KEY in source:
            self.__source = mm_util.normalize_package_path(source[FileTask.SOURCE_KEY])

        if FileTask.TARGET_KEY in source:
            self.__target = mm_util.normalize_package_path(source[FileTask.TARGET_KEY])

        if FileTask.REQUIRE_TARGET_KEY in source:
            self.__require_target = mm_util.boolean(source[FileTask.REQUIRE_TARGET_KEY])

    def export(self):
        node = super().export()

        node[FileTask.SOURCE_KEY] = self.source
        node[FileTask.TARGET_KEY] = self.target
        node[FileTask.REQUIRE_TARGET_KEY] = self.require_target
        return node

    def list_resources(self):
        resources = super().list_resources()
        resources.append(self.source)

        return resources

    def validate(self, context):
        result = super().validate(context)

        if not context.source_filesystem.file_exists(self.source):
            context.add_error(f"source file not present in source filesystem: {self.source}, {context.source_filesystem}")
            result = False

        if self.require_target and not context.target_filesystem.file_exists(self.target):
            context.add_error(f"target file not present in target filesystem: {self.target}, {context.target_filesystem}")
            result = False

        return result

    def apply(self, context):
        result = super().apply(context)

        if self.validate(context):
            # TODO: add some kind of tracking to determine task path
            # TODO: make this atomic!!
            log.debug("Running task \"%s\":", self.name)
            log.debug("  copying file %s to %s", context.source_filesystem.file_abspath(self.source), context.target_filesystem.file_abspath(self.target))

            with context.source_filesystem.open(self.source, 'rb') as source:
                with context.target_filesystem.open(self.target, 'wb') as target:
                    shutil.copyfileobj(source, target)



class SpriteTask(Task):
    SOURCE_KEY="source"

    SPRITE_SHEET_KEY="sprite_sheet"
    SPRITE_MAP_KEY="sprite_map"
    SPRITE_KEY="sprite"

    MAX_SPRITE_LENGTH=128

    def __init__(self):
        super().__init__("sprite")

    def reset(self):
        super().reset()

        self.__source = None
        self.__sprite_sheet = None
        self.__sprite_map = None
        self.__sprite = None

    @property
    def source(self):
        return self.__source

    @property
    def sprite_sheet(self):
        return self.__sprite_sheet

    @property
    def sprite_map(self):
        return self.__sprite_map

    @property
    def sprite(self):
        return self.__sprite

    def populate(self, source):
        super().populate(source)

        if SpriteTask.SOURCE_KEY in source:
            self.__source = mm_util.normalize_package_path(source[SpriteTask.SOURCE_KEY])

        if SpriteTask.SPRITE_SHEET_KEY in source:
            self.__sprite_sheet = mm_util.normalize_package_path(source[SpriteTask.SPRITE_SHEET_KEY])

        if SpriteTask.SPRITE_MAP_KEY in source:
            self.__sprite_map = mm_util.normalize_package_path(source[SpriteTask.SPRITE_MAP_KEY])

        if SpriteTask.SPRITE_KEY in source:
            self.__sprite = mm_util.normalize_str(source[SpriteTask.SPRITE_KEY], SpriteTask.MAX_SPRITE_LENGTH)

    def export(self):
        node = super().export()

        node[SpriteTask.SOURCE_KEY] = self.source
        node[SpriteTask.SPRITE_SHEET_KEY] = self.sprite_sheet
        node[SpriteTask.SPRITE_MAP_KEY] = self.sprite_map
        node[SpriteTask.SPRITE_KEY] = self.sprite

        return node

    def list_resources(self):
        resources = super().list_resources()
        resources.append(self.source)

        return resources

    def validate(self, context):
        result = super().validate(context)

        if not context.source_filesystem.file_exists(self.source):
            context.add_error(f"source file not present in source filesystem: {self.source}, {context.source_filesystem}")
            result = False

        if not context.target_filesystem.file_exists(self.sprite_sheet):
            context.add_error(f"target sprite sheet not present in target filesystem: {self.sprite_sheet}, {context.target_filesystem}")
            result = False

        if not context.target_filesystem.file_exists(self.sprite_map):
            context.add_error(f"target sprite map not present in target filesystem: {self.sprite_map}, {context.target_filesystem}")
            result = False

        if not mm_util.sprite_exists_in_map(context.target_filesystem, self.sprite_map, self.sprite):
            context.add_error(f"target sprite map does not contain the target sprite: {self.sprite_map}, {self.sprite}")
            result = False

        return result

    def apply(self, context):
        raise NotImplementedError("sprite tasks not yet supported")






class Manifest(ManifestNode):
    DEFAULT_AUTHOR="unknown"

    AUTHOR_KEY="author"
    TASKS_KEY="tasks"

    MAX_AUTHOR_LENGTH=512

    def __init__(self, mod_package):
        if not isinstance(mod_package, ModPackage):
            raise TypeError("mod_package must be a type derived from the ModPackage class")

        self.__mod_package = mod_package

        super().__init__()

    def __str__(self):
        return f"Manifest [name: {self.name}, author: {self.author}, desc: {str(self.desc)[:32]} tasks: {', '.join([str(task) for task in self.tasks])}]"

    def reset(self):
        super().reset()

        self.__author = Manifest.DEFAULT_AUTHOR
        self.__tasks = []

    @property
    def author(self):
        return self.__author

    @property
    def mod_package(self):
        return self.__mod_package

    @property
    def tasks(self):
        return tuple(self.__tasks)

    def add_task(self, task):
        if not isinstance(task, Task):
            raise TypeError("task must be a type derived from the Task class")

        # Post process task...? Probs nothing to do here

        self.__tasks.append(task)

    def populate(self, source):
        # TODO: This is awful, not atomic, and will propagate errors up unchecked. Blech.
        # Maybe make manifests immutable? Would then need a builder to do things reasonably though...
        # Something needs to be done here so manifest construction doesn't have to be done in a hash
        # outside the manifest object. Doesn't make a ton of sense to do it this way.
        super().populate(source)

        if Manifest.AUTHOR_KEY in source:
            self.__author = mm_util.normalize_str(source[Manifest.AUTHOR_KEY], Manifest.MAX_AUTHOR_LENGTH)

        if Manifest.TASKS_KEY in source:
            if isinstance(source[Manifest.TASKS_KEY], (list, tuple)):
                for task_node in source[Manifest.TASKS_KEY]:
                    self.add_task(self.mod_package.task_factory.build_from_node(task_node))
            else:
                # TODO: make this a bit bail out a bit cleaner so we can scold the user with all
                # errors at the same time, instead of forcing them to deal with things individually
                # Maybe just silently march on and let the validate method handle this state?
                raise TypeError("tasks is not an iterable value")

    def export(self):
        node = super().export()

        node[Manifest.AUTHOR_KEY] = self.author
        node[Manifest.TASKS_KEY] = [task.export() for task in self.tasks]

        return node

    def list_resources(self):
        resources = super().list_resources()

        for task in self.tasks:
            resources.extend(task.list_resources())

        return resources

    def validate(self, context):
        result = super().validate(context)

        # TODO: add any local validations necessary

        for task in self.tasks:
            result = result and task.validate(context)

        return result

    def apply(self, context):
        result = super().apply(context)

        # TODO: add any local applications necessary

        for task in self.tasks:
            result = result and task.apply(context)

        return result



class ModPackage():
    MANIFEST_FILENAME="manifest_v1.yaml"

    def __init__(self, task_factory, source_filesystem):
        if not isinstance(task_factory, TaskFactory):
            raise TypeError("task_factory must be a type derived from the TaskFactory class")

        if not isinstance(source_filesystem, FileSystem):
            raise TypeError("source_filesystem must be a type derived from the FileSystem class")

        self.__task_factory = task_factory
        self.__source_filesystem = source_filesystem

        self.reset()

    def reset(self):
        self.__manifest = None

    # TODO:
    # - signature stuff (creation, validation)

    @property
    def name(self):
        # Attempt to use the manifest's name first, if defined
        if self.manifest is not None and self.manifest.name is not None:
            return self.manifest.name

        # Use the source filesystem as a backup
        return self.source_filesystem.name

    @property
    def task_factory(self):
        return self.__task_factory

    @property
    def source_filesystem(self):
        return self.__source_filesystem

    @property
    def manifest(self):
        return self.__manifest

    def validate(self, target_filesystem):
        # return boolean, collect errors in context or something
        # should this also validate the signature if present, or should that be a separate method?
        # raise NotImplementedError("not yet implemented")

        context = Context(self.source_filesystem, target_filesystem)
        self.manifest.validate(context)

        return context

    def apply(self, target_filesystem):
        context = Context(self.source_filesystem, target_filesystem)
        self.manifest.apply(context)

        return context

    def read_from_filesystem(self):
        if not self.source_filesystem.exists():
            raise RuntimeError(f"cannot read package from non-existent filesystem: {self.source_filesystem.path}")

        if not self.source_filesystem.file_exists(ModPackage.MANIFEST_FILENAME):
            raise RuntimeError(f"cannot import manifest: {ModPackage.MANIFEST_FILENAME} does not exist")

        with self.source_filesystem.open(ModPackage.MANIFEST_FILENAME, 'r') as manifest_file:
            manifest_node = yaml.safe_load(manifest_file)

            self.__manifest = Manifest(self)
            self.__manifest.populate(manifest_node)

    def write_to_filesystem(self, target_filesystem):
        if not isinstance(target_filesystem, FileSystem):
            raise TypeError("target_filesystem must be a type derived from the FileSystem class")

        # If there were no problems gathering our data, create the filesystem target and start
        # writing files
        log.debug("Creating target filesystem: %s", target_filesystem)
        target_filesystem.create()

        # Write manifest
        log.debug("Writing manifest file: %s", ModPackage.MANIFEST_FILENAME)
        with target_filesystem.open(ModPackage.MANIFEST_FILENAME, 'w') as file:
            manifest_data = self.manifest.export()
            yaml.safe_dump(manifest_data, file)

        # Copy resources
        for resource in self.manifest.list_resources():
            log.debug("Writing resource: %s", resource)

            with self.source_filesystem.open(resource, 'rb') as source:
                with target_filesystem.open(resource, 'wb') as target:
                    shutil.copyfileobj(source, target)

        log.debug("mod package written successfully");
        return True
