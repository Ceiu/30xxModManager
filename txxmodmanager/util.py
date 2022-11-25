#!/usr/bin/env python3

# Utility functions that should probably live somewhere else

import os
import re
import sys
import xml.sax

from txxmodmanager.filesystem import DirectoryFS
from txxmodmanager.filesystem import PackageFS


def normalize_str(val, length=None):
    """Utility function to ensure a value is a string without leading or trailing whitespace, and,
    optionally, is no longer than the given length"""
    return str(val).strip()[:length]


def boolean(val):
    """converts a value to a boolean, returning True if the lowercase string representation is
    either 'true', or 'yes'; False otherwise"""
    return str(val).lower() in ["true", "yes"]


def default_game_directory():
    if sys.platform.startswith('win'):
        return 'C:\\Program Files (x86)\\Steam\\steamapps\\common\\30XX'

    if sys.platform.startswith('linux'):
        return os.path.expanduser('~/.local/share/Steam/SteamApps/common/30XX')

    # TODO: FIXME: should this raise an error instead?
    return None


def sanitize_filename(filename):
    # lowercase the manifest name, replace spaces with underscores
    filename = str(filename).lower().replace(' ', '_')

    # Remove non-ASCII characters
    filename = str(filename.encode('ascii', 'ignore'), 'ascii')

    # remove special characters (TODO: is there a more gooder way to do this?)
    # TODO: Might be safest to only include alphanumeric characters and underscore, rather than
    # having an exclude-list
    chars = '\'"%:/,.\\[]<>*?'
    for char in chars:
        filename = filename.replace(char, '')

    return filename


def normalize_package_path(path, max_len=256):
    """normalizes a path specifically for the format used within mod packages"""

    # Path could be Windows or POSIX, but we need to output a POSIX path relative to a given root.
    # While not technically accurate, if we always output rooted paths, we can logically treat
    # packages as a chroot jail in terms of mod packages.

    # pathlib kinda sucks for this, so we'll just do the replacements ourselves
    parts = re.split(r":|\\|/", os.path.normpath(str(path).strip()[:max_len]))

    return '/' + '/'.join(filter(None, parts))


def get_filesystem(root):
    """Attempts to build an appropriate filesystem object for a given root path"""

    # Check if we appear to be referencing an archive:
    if re.search('\.zip\Z', root, re.I):
        return PackageFS(root)

    # Check if we appear to be referencing a manifest file directly
    if re.search('\.ya?ml\Z', root, re.I):
        return DirectoryFS(os.path.dirname(root))

    # Probably a directory reference
    return DirectoryFS(root)



def sprite_exists_in_map(filesystem, sprite_map, sprite):
    sprite_finder = SpriteFinder(sprite)

    parser = xml.sax.make_parser()
    parser.setFeature(xml.sax.handler.feature_namespaces, False)
    parser.setContentHandler(sprite_finder)

    with filesystem.open(sprite_map, 'r') as file:
        parser.parse(file)

    return sprite_finder.found


class SpriteFinder(xml.sax.ContentHandler):
    def __init__(self, target):
        self.__target = str(target)
        self.__found = False
        self.__stack = []

    @property
    def current_path(self):
        return '.'.join(self.__stack)

    @property
    def found(self):
        return self.__found

    def startElement(self, tag, attributes):
        self.__stack.append(tag)

        # Nothing more to do, don't bother doing other, more expensive, operations
        if self.__found:
            return

        if self.current_path.lower() == "subtexture.textureatlas":
            if "name" in attributes and attributes["name"] == self.__target:
                self.__found = True

    def endElement(self, tag):
        self.__stack.pop()
