#!/usr/bin/env python3

import logging
import os
import zipfile

from contextlib import contextmanager
from io import TextIOWrapper
from txxmodmanager import util as mm_util
from zipfile import ZipFile
from zipfile import Path as ZipPath


# This is assumed to be setup before the package is imported; otherwise we get ugly defaults
log = logging.getLogger('TxxModManager')


class FileSystem():
    def __init__(self, path):
        self.__path = os.path.realpath(path)

    def __str__(self):
        return f"{self.__class__.__name__} [path: {self.path}]"

    @property
    def path(self):
        return self.__path

    @property
    def name(self):
        raise NotImplementedError("abstract method not yet implemented")

    def exists(self):
        return os.path.exists(self.path)

    def create(self):
        raise NotImplementedError("abstract method not yet implemented")

    @contextmanager
    def open(self, filename, mode = 'r'):
        raise NotImplementedError("abstract method not yet implemented")

    def file_exists(self, filename):
        raise NotImplementedError("abstract method not yet implemented")

    def is_file(self, path):
        raise NotImplementedError("abstract method not yet implemented")

    def is_dir(self, path):
        raise NotImplementedError("abstract method not yet implemented")

    def file_abspath(self, path):
        raise NotImplementedError("abstract method not yet implemented")



class PackageFS(FileSystem):
    def __init__(self, path):
        super().__init__(path)

    @property
    def name(self):
        basename = os.path.basename(self.path)
        return basename.rsplit('.', 2)[0]

    def create(self):
        directory = os.path.dirname(self.path)

        # Create our base directory structure as necessary
        os.makedirs(directory, exist_ok=True)

        # Create the archive, truncating the file if it already exists
        with open(self.path, 'w') as archive:
            pass

    def normalize_path(self, path):
        path = str(path)

        # Annoyingly, having a leading slash appears to add a "fake" directory (named "_") on some
        # archive viewers. If it's present, remove it.
        if path[0] == '/':
            path = path[1:]

        return path

    @contextmanager
    def open(self, filename, mode = 'r'):
        # impl note: ZipFiles don't support non-binary modes, so we'll try to fake it best we can
        binary = False
        if mode.endswith('b'):
            binary = True
            mode = mode[:-1]

        with ZipFile(self.path, 'a') as archive:
            with archive.open(self.normalize_path(filename), mode) as file:
                if not binary:
                    file = TextIOWrapper(file)

                yield file

    def file_exists(self, path):
        with ZipFile(self.path, 'r') as archive:
            return ZipPath(archive, self.normalize_path(path)).exists()

    def is_file(self, path):
        with ZipFile(self.path, 'r') as archive:
            return ZipPath(archive, self.normalize_path(path)).is_file()

    def is_dir(self, path):
        with ZipFile(self.path, 'r') as archive:
            return ZipPath(archive, self.normalize_path(path)).is_dir()

    def file_abspath(self, path):
        normalized = mm_util.normalize_package_path(path)
        return f"{self.path}${normalized}"



class DirectoryFS(FileSystem):
    def __init__(self, path):
        super().__init__(path)

    @property
    def name(self):
        return os.path.basename(self.path)

    def create(self):
        os.makedirs(self.path, exist_ok=True)

    @contextmanager
    def open(self, filename, mode = 'r'):
        with open(self.file_abspath(filename), mode) as file:
            yield file

    def file_exists(self, filename):
        return os.path.exists(self.file_abspath(filename))

    def is_file(self, path):
        return os.path.is_file(self.file_abspath(filename))

    def is_dir(self, path):
        return os.path.is_dir(self.file_abspath(filename))

    def file_abspath(self, path):
        # impl note: we're expecting normpath to do *a lot* of heavy lifting here
        return os.path.normpath(f"{self.path}/{path}")

