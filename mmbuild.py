#!/usr/bin/env python

# TODO: Write file header

import argparse
# import datetime
import logging
# import json
import os
# import random
# import re
# import requests
# import string
import sys
# import time

from pprint import pprint

from txxmodmanager import manifest_v1 as mm_manifest_v1
from txxmodmanager import filesystem as mm_fs
from txxmodmanager import util as mm_util





def build_logger(name, msg_format):
    """Builds and configures our logger"""
    class EmptyLineFilter(logging.Filter):
        """Logging filter implementation that filters on empty or whitespace-only lines"""
        def __init__(self, invert=False):
            self.invert = invert

        def filter(self, record):
            result = bool(record.msg) and not record.msg.isspace()
            if self.invert:
                result = not result

            return result

    # Create the base/standard handler
    std_handler = logging.StreamHandler(sys.stdout)
    std_handler.setFormatter(logging.Formatter(fmt=msg_format))
    std_handler.addFilter(EmptyLineFilter())

    # Create an empty-line handler
    empty_handler = logging.StreamHandler(sys.stdout)
    empty_handler.setFormatter(logging.Formatter(fmt=''))
    empty_handler.addFilter(EmptyLineFilter(True))

    # Create a logger using the above handlers
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.addHandler(std_handler)
    logger.addHandler(empty_handler)

    return logger

log = build_logger('TxxModManager', '%(asctime)-15s %(levelname)-7s %(name)s -- %(message)s')





def parse_options():
    class MultiLineFormatter(argparse.HelpFormatter):
        """Formatter that provides multi-line support to the standard help formatter"""
        def _split_lines(self, text, width):
            return [elem for line in text.splitlines() for elem in argparse.HelpFormatter._split_lines(self, line, width)]

    parser = argparse.ArgumentParser(prog='mmbuild', description='Validates and builds 30XX mod packages', add_help=True, formatter_class=MultiLineFormatter)

    parser.add_argument('--debug', action='store_true', default=False,
        help='enables debug output')

    parser.add_argument('--out', action='store', dest='target', default=None,
        help='the location and name of the generated mod package; defaults to the name of the mod indicated in the manifest')

    parser.add_argument('--validate_only', action='store_true', default=False,
        help='indicates that the target manifest should only be validated, and no mod package should be created; defaults to false')

    parser.add_argument('--game_dir', action='store', default=None,
        help='specifies the location of the game directory to use for validating the mod package before creation; defaults to:\n' +
            '- Linux:   ~/.local/share/Steam/SteamApps/common/30XX\n' +
            '- Windows: C:\\Program Files (x86)\\Steam\\steamapps\\common\\30XX')

    parser.add_argument('source', action='store',
        help='the source manifest to build; must be a path to a manifest yaml file or directory containing it')

    # parse & process...
    options = parser.parse_args()

    # Set logging level as appropriate
    if options.debug:
        log.setLevel(logging.DEBUG)

    # sort out default game directory
    if options.game_dir is None:
        options.game_dir = mm_util.default_game_directory()

        # fail if we don't have a default for this system
        if options.game_dir is None:
            log.error(f"Unable to determine default game directory automatically. Game directory must be provided with the --game_dir option.")
            sys.exit(1)

    # TODO:
    # Should probably move validations out to another function
    if not os.path.exists(options.game_dir):
        log.error("game directory does not exist: %s", options.game_dir)
        sys.exit(1)

    # Check that we have a valid source path & normalize it to an absolute path
    if not os.path.exists(options.source):
        log.error("source path does not exist: %s", options.source)
        sys.exit(1)

    options.source = os.path.abspath(options.source)

    return options


def generate_output_filename(package):
    # Use the mod name as the filename, but sanitize the goofy characters out
    filename = mm_util.sanitize_filename(package.name)

    # append package file extension and return
    return f"{filename}.zip"


def main():
    """Intended script entry point; actual business logic starts here, probably"""
    options = parse_options()

    # TODO: Clean up error handling here for a better user experience
    source_filesystem = mm_util.get_filesystem(options.source)
    game_filesystem = mm_fs.DirectoryFS(options.game_dir)

    # TODO:
    # Check if the filesystem is already a zipped up package. If so, just validate it without building
    # a new package?

    task_factory = mm_manifest_v1.TaskFactory()

    # TODO:
    # Add custom task handlers to our task factory

    log.info("Reading mod package @ %s", source_filesystem.path)

    package = mm_manifest_v1.ModPackage(task_factory, source_filesystem)
    package.read_from_filesystem()

    log.info("Validating package against install @ %s", game_filesystem.path)
    context = package.validate(game_filesystem)

    if len(context.errors) > 0:
        log.error("Mod package has 1 or more errors which require resolution:")

        for error in context.errors:
            log.error(error)

        log.error("")
        log.error("%s error(s), %s warning(s)", len(context.errors), len(context.warnings))
        sys.exit(1)

    log.info("Package appears to be valid")

    # If we're only doing validations, exit here
    if options.validate_only:
        sys.exit(0)

    # If the user hasn't specified a target for output, use the mod's name as the basis for the
    # generated name
    if options.target is None:
        options.target = generate_output_filename(package)

    target_filesystem = mm_fs.PackageFS(options.target)

    log.info("Building mod package %s @ %s", package.name, target_filesystem.path)

    package.write_to_filesystem(target_filesystem)




if __name__ == '__main__':
    main()
